"""Testes do sinal do valor e da traducao de categoria.

Dois defeitos de ingestao, ambos vindos de ler o payload da Pluggy sem normalizar.

**Sinal.** A Pluggy assina `amount` e a convencao difere entre conta e cartao: em
conta a saida e negativa; em cartao a compra e positiva e o pagamento da fatura e
negativo. `type` (DEBIT/CREDIT) e o indicador confiavel, e e obrigatorio.
Guardar com sinal produzia tres sintomas de uma vez: despesa somando negativo (taxa
de poupanca acima de 100%), "-" da tela virando "--", e reconciliacao de assinatura
que nunca casa porque filtra `amount__gt=0`.

**Idioma.** A taxonomia do categorizador da Pluggy e em ingles, e o texto ia direto
para a tela.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.finance.categories import (
    CATEGORY_EXPENSES,
    CATEGORY_INCOME,
    CATEGORY_UNCATEGORIZED,
    translate_category,
)
from apps.finance.consolidation import build_monthly_cash_flow
from apps.finance.domain import normalize_transaction_category
from apps.finance.models import (
    CategorizationRule,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
    Transaction,
    TransactionType,
)
from apps.finance.tasks import _due_date_for, _reconcile_subscriptions, _upsert_transaction

# --------------------------------------------------------------------------
# Traducao: pura, roda sem banco
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("english", "portuguese"),
    [
        ("Bookstore", "Livraria"),
        ("Vehicle maintenance", "Manutenção de veículo"),
        ("Digital services", "Serviços digitais"),
        ("Housing", "Moradia"),
        ("Kindergarten", "Educação infantil"),
        ("Clothing", "Vestuário"),
        ("Groceries", "Supermercado"),
        ("Food delivery", "Delivery de comida"),
        ("Transfer - PIX", "Transferência - PIX"),
        ("Credit card payment", "Pagamento de cartão de crédito"),
    ],
)
def test_documented_categories_are_translated(english, portuguese):
    assert translate_category(english) == portuguese


def test_translation_ignores_case_and_padding():
    """Os nomes vem do provedor; nao ha garantia de capitalizacao estavel."""
    assert translate_category("  bOOkstore  ") == "Livraria"


def test_unknown_category_passes_through_instead_of_becoming_generic():
    """Categoria nova da Pluggy aparece em ingles -- visivel e corrigivel -- em vez
    de virar "Outros" e se misturar ao resto."""
    assert translate_category("Something Brand New") == "Something Brand New"


def test_empty_category_stays_empty():
    assert translate_category("") == ""
    assert translate_category(None) == ""


# --------------------------------------------------------------------------
# Categoria na ingestao
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_provider_category_is_translated(user):
    assert (
        normalize_transaction_category("QUALQUER", "Bookstore", TransactionType.DEBIT, user=user)
        == "Livraria"
    )


@pytest.mark.django_db
def test_user_rule_still_wins_over_the_translated_provider_category(user):
    CategorizationRule.objects.create(user=user, pattern="livraria x", category="Meus livros")

    category = normalize_transaction_category(
        "LIVRARIA X compra", "Bookstore", TransactionType.DEBIT, user=user
    )

    assert category == "Meus livros"


@pytest.mark.django_db
def test_keyword_fallback_is_in_portuguese(user):
    assert (
        normalize_transaction_category("UBER TRIP", "", TransactionType.DEBIT, user=user)
        == "Transporte"
    )


@pytest.mark.django_db
def test_type_fallback_is_in_portuguese(user):
    assert (
        normalize_transaction_category("xyz sem pista", "", TransactionType.DEBIT, user=user)
        == CATEGORY_EXPENSES
    )
    assert (
        normalize_transaction_category("xyz sem pista", "", TransactionType.CREDIT, user=user)
        == CATEGORY_INCOME
    )


@pytest.mark.django_db
def test_unknown_type_falls_back_to_the_portuguese_default(user):
    assert normalize_transaction_category("xyz", "", "outro", user=user) == CATEGORY_UNCATEGORIZED


# --------------------------------------------------------------------------
# Sinal do valor
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_negative_bank_debit_is_stored_as_magnitude(user, account):
    """Conta bancaria: saida chega negativa da Pluggy."""
    _upsert_transaction(
        {
            "id": "tx-neg",
            "description": "Compra no mercado",
            "amount": -4658.84,
            "type": "DEBIT",
            "date": "2026-08-10T12:00:00.000Z",
        },
        account=account,
        card=None,
        user=user,
    )

    tx = Transaction.objects.get(external_id="tx-neg")
    assert tx.amount == Decimal("4658.84")
    assert tx.type == TransactionType.DEBIT


@pytest.mark.django_db
def test_positive_card_purchase_stays_positive(user, connection):
    """Cartao: compra chega positiva. A magnitude e a mesma nos dois casos."""
    from apps.finance.models import Card

    card = Card.objects.create(connection=connection, external_id="card-sign", name="Cartao")
    _upsert_transaction(
        {
            "id": "tx-card-pos",
            "description": "Compra no cartao",
            "amount": 75.0,
            "type": "DEBIT",
            "date": "2026-08-10T12:00:00.000Z",
        },
        account=None,
        card=card,
        user=user,
    )

    assert Transaction.objects.get(external_id="tx-card-pos").amount == Decimal("75.00")


@pytest.mark.django_db
def test_card_bill_payment_arrives_negative_and_is_stored_as_magnitude(user, connection):
    from apps.finance.models import Card

    card = Card.objects.create(connection=connection, external_id="card-pay", name="Cartao")
    _upsert_transaction(
        {
            "id": "tx-card-pay",
            "description": "Pagamento da fatura",
            "amount": -150.0,
            "type": "CREDIT",
            "date": "2026-08-10T12:00:00.000Z",
        },
        account=None,
        card=card,
        user=user,
    )

    tx = Transaction.objects.get(external_id="tx-card-pay")
    assert tx.amount == Decimal("150.00")
    assert tx.type == TransactionType.CREDIT


@pytest.mark.django_db
def test_savings_rate_stays_within_100_percent(user, account):
    """Despesa negativa fazia `savings = receita - (negativo)` estourar a receita, e
    a taxa de poupanca aparecia como 213% ou 350%."""
    _upsert_transaction(
        {
            "id": "tx-in",
            "description": "Salario",
            "amount": 5000.0,
            "type": "CREDIT",
            "date": "2026-08-05T12:00:00.000Z",
        },
        account=account,
        card=None,
        user=user,
    )
    _upsert_transaction(
        {
            "id": "tx-out",
            "description": "Aluguel",
            "amount": -2000.0,
            "type": "DEBIT",
            "date": "2026-08-06T12:00:00.000Z",
        },
        account=account,
        card=None,
        user=user,
    )

    flow = build_monthly_cash_flow(user, year=2026, month=8)

    assert flow["income"] == Decimal("5000.00")
    assert flow["expenses"] == Decimal("2000.00")
    assert flow["savings"] == Decimal("3000.00")
    assert 0 <= flow["savings_rate"] <= 100


@pytest.mark.django_db
def test_subscription_reconciliation_matches_a_negative_debit(user, account):
    """`_reconcile_subscriptions` filtra `amount__gt=0`. Com o valor negativo, o
    pagamento nunca casava e a assinatura ficava eternamente pendente."""
    subscription = Subscription.objects.create(
        user=user,
        name="Netflix",
        category=SubscriptionCategory.STREAMING,
        amount=Decimal("55.00"),
        due_day=10,
    )
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, 10)

    _upsert_transaction(
        {
            "id": "tx-netflix-neg",
            "description": "NETFLIX assinatura",
            "amount": -55.0,
            "type": "DEBIT",
            "date": f"{due_date.isoformat()}T12:00:00.000Z",
        },
        account=account,
        card=None,
        user=user,
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.paid_amount == Decimal("55.00")
