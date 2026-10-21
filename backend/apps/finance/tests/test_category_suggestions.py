"""Testes da sugestao de categoria para PIX.

Cobrem: validacao da resposta do modelo (nada fora da taxonomia chega ao banco),
reaproveitamento por contraparte (uma chamada por nome), limite de chamadas,
aceitacao que vira categoria manual + regra, e a recusa de inferencia remota.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance import category_suggestions as cs
from apps.finance.ai_services import AIServiceUnavailable
from apps.finance.models import CategorizationRule, Transaction, TransactionType

ALLOWED = cs.allowed_categories()


class FakeSuggester:
    def __init__(self, answers=None):
        self.answers = {cs.normalize_name(k): v for k, v in (answers or {}).items()}
        self.calls: list[str] = []

    def predict(self, name, description, tx_type):
        self.calls.append(name)
        return self.answers.get(cs.normalize_name(name))


def make_pix(
    account, external_id, name, *, category="PIX", manual=False, tx_type=TransactionType.DEBIT
):
    receiver_or_payer = {"name": name, "document": "***.123.456-**"}
    key = "payment_receiver" if tx_type == TransactionType.DEBIT else "payment_payer"
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description=f"Transferência - Pix - {name}",
        amount=Decimal("40.00"),
        type=tx_type,
        category=category,
        category_is_manual=manual,
        provider_category="Transfer - Pix",
        payment_method="PIX",
        booked_at=timezone.now(),
        **{key: receiver_or_payer},
    )


# --------------------------------------------------------------------------
# Resposta do modelo
# --------------------------------------------------------------------------


def test_valid_answer_is_canonicalized_to_taxonomy_name():
    prediction = cs.parse_suggestion('{"category": "alimentação", "confidence": 0.8}', ALLOWED)
    assert prediction == cs.CategoryPrediction("Alimentação", 0.8)


def test_category_outside_taxonomy_is_rejected():
    assert cs.parse_suggestion('{"category": "Inventada", "confidence": 0.9}', ALLOWED) is None


def test_null_category_means_no_suggestion():
    assert cs.parse_suggestion('{"category": null, "confidence": 0.1}', ALLOWED) is None


@pytest.mark.parametrize("raw", ["", "não é json", "[1, 2]", '{"category": 5}'])
def test_malformed_answers_are_ignored(raw):
    assert cs.parse_suggestion(raw, ALLOWED) is None


def test_confidence_is_clamped_to_unit_interval():
    high = cs.parse_suggestion('{"category": "Alimentação", "confidence": 7}', ALLOWED)
    low = cs.parse_suggestion('{"category": "Alimentação", "confidence": -3}', ALLOWED)
    assert high.confidence == 1.0
    assert low.confidence == 0.0


def test_excluded_categories_are_never_suggested():
    assert "transferência entre contas próprias" not in ALLOWED
    assert "pix" not in ALLOWED


# --------------------------------------------------------------------------
# Nome da contraparte
# --------------------------------------------------------------------------


def test_normalize_name_ignores_case_accents_and_spacing():
    assert cs.normalize_name("  João   da Silva ") == cs.normalize_name("JOAO DA SILVA")


def test_counterparty_is_receiver_for_outgoing_and_payer_for_incoming(account):
    out = make_pix(account, "out-1", "Padaria Central", tx_type=TransactionType.DEBIT)
    assert cs.counterparty_name(out) == "Padaria Central"

    incoming = Transaction.objects.create(
        account=account,
        external_id="in-1",
        description="Transferência recebida",
        amount=Decimal("10"),
        type=TransactionType.CREDIT,
        payment_method="PIX",
        payment_payer={"name": "Maria Souza"},
        booked_at=timezone.now(),
    )
    assert cs.counterparty_name(incoming) == "Maria Souza"


# --------------------------------------------------------------------------
# Lote
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_batch_suggests_without_changing_category(user, account):
    tx = make_pix(account, "tx-1", "Padaria Central")
    suggester = FakeSuggester({"Padaria Central": cs.CategoryPrediction("Alimentação", 0.9)})

    result = cs.suggest_categories(user, suggester)

    tx.refresh_from_db()
    assert tx.suggested_category == "Alimentação"
    assert tx.suggested_category_confidence == 0.9
    assert tx.category == "PIX"
    assert result.suggested == 1


@pytest.mark.django_db
def test_same_counterparty_calls_the_model_once(user, account):
    make_pix(account, "tx-1", "Padaria Central")
    make_pix(account, "tx-2", "padaria central")
    suggester = FakeSuggester({"Padaria Central": cs.CategoryPrediction("Alimentação", 0.9)})

    result = cs.suggest_categories(user, suggester)

    assert len(suggester.calls) == 1
    assert result.reused == 1
    assert Transaction.objects.filter(suggested_category="Alimentação").count() == 2


@pytest.mark.django_db
def test_manual_choice_for_a_counterparty_is_reused_without_model(user, account):
    make_pix(account, "manual", "Posto Sul", category="Transporte", manual=True)
    target = make_pix(account, "auto", "Posto Sul")
    suggester = FakeSuggester()

    cs.suggest_categories(user, suggester)

    target.refresh_from_db()
    assert suggester.calls == []
    assert target.suggested_category == "Transporte"


@pytest.mark.django_db
def test_limit_caps_model_calls_but_not_reuse(user, account):
    make_pix(account, "a1", "Pessoa A")
    make_pix(account, "b1", "Pessoa B")
    make_pix(account, "b2", "Pessoa B")
    suggester = FakeSuggester(
        {
            "Pessoa A": cs.CategoryPrediction("Alimentação", 0.5),
            "Pessoa B": cs.CategoryPrediction("Lazer", 0.5),
        }
    )

    result = cs.suggest_categories(user, suggester, limit=1)

    assert len(suggester.calls) == 1
    assert result.calls == 1
    called = cs.normalize_name(suggester.calls[0])
    for tx in Transaction.objects.all():
        if cs.normalize_name(cs.counterparty_name(tx)) == called:
            expected = "Alimentação" if called == "PESSOA A" else "Lazer"
            assert tx.suggested_category == expected
        else:
            assert tx.suggested_category == ""


@pytest.mark.django_db
def test_unmatched_counterparty_is_not_asked_again_in_same_batch(user, account):
    make_pix(account, "x1", "Fulano")
    make_pix(account, "x2", "Fulano")
    suggester = FakeSuggester()

    result = cs.suggest_categories(user, suggester)

    assert suggester.calls == ["Fulano"]
    assert result.unmatched == 2


@pytest.mark.django_db
def test_real_provider_category_is_preserved(user, account):
    make_pix(account, "sup-1", "Mercado Y", category="Supermercado")
    suggester = FakeSuggester({"Mercado Y": cs.CategoryPrediction("Alimentação", 0.9)})

    cs.suggest_categories(user, suggester)

    assert suggester.calls == []


@pytest.mark.django_db
def test_suggestions_never_cross_users(user, account, django_user_model):
    other = django_user_model.objects.create_user(username="outro", password="x")
    make_pix(account, "mine", "Padaria Central", category="Transporte", manual=True)
    other_tx_suggester = FakeSuggester({"Padaria Central": cs.CategoryPrediction("Lazer", 0.5)})

    cs.suggest_categories(other, other_tx_suggester)

    assert other_tx_suggester.calls == []  # o usuario "outro" nao tem transacoes


# --------------------------------------------------------------------------
# Aceitar
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_accept_applies_category_as_manual_and_creates_rule(user, account):
    tx = make_pix(account, "tx-1", "Padaria Central")
    tx.suggested_category = "Alimentação"
    tx.suggested_category_confidence = 0.9
    tx.save()

    cs.accept_suggestion(tx, user)

    tx.refresh_from_db()
    assert tx.category == "Alimentação"
    assert tx.category_is_manual is True
    assert tx.suggested_category == ""
    rule = CategorizationRule.objects.get(user=user)
    assert rule.pattern == "padaria central"
    assert rule.category == "Alimentação"


@pytest.mark.django_db
def test_accept_does_not_duplicate_existing_rule(user, account):
    CategorizationRule.objects.create(user=user, pattern="Padaria Central", category="Lazer")
    tx = make_pix(account, "tx-1", "Padaria Central")
    tx.suggested_category = "Alimentação"
    tx.save()

    cs.accept_suggestion(tx, user)

    assert CategorizationRule.objects.filter(user=user).count() == 1


# --------------------------------------------------------------------------
# Endpoints e moderacao
# --------------------------------------------------------------------------


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_remote_inference_is_refused_before_any_call(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "https://api.externo.example")
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)

    with pytest.raises(AIServiceUnavailable):
        cs.CategorySuggester()


@pytest.mark.django_db
def test_suggest_endpoint_returns_503_when_model_is_unavailable(api, monkeypatch):
    def unavailable():
        raise AIServiceUnavailable("Ollama fora do ar")

    monkeypatch.setattr(cs, "CategorySuggester", unavailable)

    response = api.post("/api/v1/transactions/suggest-categories/", {}, format="json")

    assert response.status_code == 503
    assert "Ollama" in response.data["error"]


@pytest.mark.django_db
def test_accept_endpoint_rejects_transaction_without_suggestion(api, user, account):
    tx = make_pix(account, "tx-1", "Padaria Central")

    response = api.post(f"/api/v1/transactions/{tx.id}/accept-suggestion/")

    assert response.status_code == 400


@pytest.mark.django_db
def test_accept_endpoint_applies_the_suggestion(api, user, account):
    tx = make_pix(account, "tx-1", "Padaria Central")
    tx.suggested_category = "Alimentação"
    tx.save()

    response = api.post(f"/api/v1/transactions/{tx.id}/accept-suggestion/")

    assert response.status_code == 200
    assert response.data["category"] == "Alimentação"
    assert response.data["category_is_manual"] is True
