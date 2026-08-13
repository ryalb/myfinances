"""Testes da edicao manual de categoria de uma transacao.

Escolher uma categoria a mao na tela de transacoes precisa sobreviver a dois
processos automaticos que rodam depois: o sync da Pluggy (que reenvia a mesma
transacao em updates incrementais) e "reaplicar regras". Sem uma marca
(`category_is_manual`), qualquer um dos dois apagaria a escolha do usuario em
silencio -- o teste de sync mora aqui; o de reaplicar regras mora em
`test_categorization_rules.py`, junto dos outros testes desse endpoint.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance import tasks
from apps.finance.models import CategorizationRule, Transaction, TransactionType


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def tx(account):
    return Transaction.objects.create(
        account=account,
        external_id="tx-manual-1",
        description="UBER TRIP centro",
        amount=Decimal("25.00"),
        type=TransactionType.DEBIT,
        category="Transportation",
        provider_category="Travel",
        booked_at=timezone.now(),
    )


def category_url(transaction) -> str:
    return f"/api/v1/transactions/{transaction.id}/category/"


# --------------------------------------------------------------------------
# PATCH: definir categoria a mao
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_patch_sets_the_category_and_marks_it_manual(api, tx):
    response = api.patch(category_url(tx), {"category": "Minha categoria"}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["category"] == "Minha categoria"
    assert response.data["category_is_manual"] is True
    tx.refresh_from_db()
    assert tx.category == "Minha categoria"
    assert tx.category_is_manual is True


@pytest.mark.django_db
def test_patch_strips_surrounding_whitespace(api, tx):
    response = api.patch(category_url(tx), {"category": "  Lazer  "}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["category"] == "Lazer"


@pytest.mark.django_db
def test_patch_rejects_a_blank_category(api, tx):
    response = api.patch(category_url(tx), {"category": "   "}, format="json")

    assert response.status_code == 400
    tx.refresh_from_db()
    assert tx.category == "Transportation"
    assert tx.category_is_manual is False


@pytest.mark.django_db
def test_patch_rejects_a_category_over_the_field_limit(api, tx):
    response = api.patch(category_url(tx), {"category": "x" * 101}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_patch_returns_404_for_another_users_transaction(api, tx, other_user):
    other_client = APIClient()
    other_client.force_authenticate(other_user)

    response = other_client.patch(category_url(tx), {"category": "Roubo"}, format="json")

    assert response.status_code == 404
    tx.refresh_from_db()
    assert tx.category == "Transportation"
    assert tx.category_is_manual is False


# --------------------------------------------------------------------------
# DELETE: voltar para a categoria automatica
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_reverts_to_the_automatic_category(api, tx, user):
    CategorizationRule.objects.create(user=user, pattern="uber", category="Transporte automatico")
    api.patch(category_url(tx), {"category": "Categoria manual"}, format="json")

    response = api.delete(category_url(tx))

    assert response.status_code == 200, response.data
    assert response.data["category"] == "Transporte automatico"
    assert response.data["category_is_manual"] is False
    tx.refresh_from_db()
    assert tx.category == "Transporte automatico"
    assert tx.category_is_manual is False


@pytest.mark.django_db
def test_delete_on_a_never_edited_transaction_recomputes_from_scratch(api, tx):
    """DELETE sem PATCH antes nao deveria dar erro -- so recalcula a categoria
    automatica, que pode ate bater com a que ja estava la."""
    response = api.delete(category_url(tx))

    assert response.status_code == 200, response.data
    assert response.data["category_is_manual"] is False


# --------------------------------------------------------------------------
# Sync nao apaga escolha manual
# --------------------------------------------------------------------------


def _pluggy_payload(tx_id: str, description: str) -> dict:
    return {
        "id": tx_id,
        "date": timezone.now().date().isoformat(),
        "amount": 25,
        "description": description,
        "currencyCode": "BRL",
        "type": "DEBIT",
        "category": "Travel",
    }


@pytest.mark.django_db
def test_sync_does_not_overwrite_a_manually_set_category(account, user):
    Transaction.objects.create(
        account=account,
        external_id="tx-sync-manual",
        description="UBER TRIP",
        amount=Decimal("25.00"),
        type=TransactionType.DEBIT,
        category="Categoria manual",
        category_is_manual=True,
        provider_category="Travel",
        booked_at=timezone.now(),
    )

    tasks._upsert_transaction(
        _pluggy_payload("tx-sync-manual", "UBER TRIP"), account=account, card=None, user=user
    )

    updated = Transaction.objects.get(external_id="tx-sync-manual")
    assert updated.category == "Categoria manual"
    assert updated.category_is_manual is True
    # O resto da linha (ex.: valor, descricao) continua sendo atualizado normalmente.
    assert updated.provider_category == "Travel"


@pytest.mark.django_db
def test_sync_still_categorizes_new_transactions_automatically(account, user):
    CategorizationRule.objects.create(user=user, pattern="uber", category="Transporte")

    tasks._upsert_transaction(
        _pluggy_payload("tx-sync-new", "UBER TRIP"), account=account, card=None, user=user
    )

    created = Transaction.objects.get(external_id="tx-sync-new")
    assert created.category == "Transporte"
    assert created.category_is_manual is False


@pytest.mark.django_db
def test_sync_recategorizes_non_manual_transactions_as_before(account, user):
    """A guarda e so para `category_is_manual=True` -- transacoes normais
    continuam sendo recategorizadas a cada sync, comportamento pre-existente."""
    Transaction.objects.create(
        account=account,
        external_id="tx-sync-auto",
        description="UBER TRIP",
        amount=Decimal("25.00"),
        type=TransactionType.DEBIT,
        category="categoria antiga",
        category_is_manual=False,
        booked_at=timezone.now(),
    )
    CategorizationRule.objects.create(user=user, pattern="uber", category="Transporte novo")

    tasks._upsert_transaction(
        _pluggy_payload("tx-sync-auto", "UBER TRIP"), account=account, card=None, user=user
    )

    updated = Transaction.objects.get(external_id="tx-sync-auto")
    assert updated.category == "Transporte novo"
