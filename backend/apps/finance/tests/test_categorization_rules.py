"""Testes das regras de categorizacao e da reaplicacao ao historico.

Duas coisas faziam o motor de regras parecer quebrado:

1. `provider_category` tinha precedencia sobre as regras do usuario. Uma regra
   "uber -> transporte" nao se aplicava se a Pluggy tivesse mandado "Travel" --
   ou seja, regra explicita do usuario perdia para heuristica do provedor.
2. As regras rodavam so no import. Criar uma regra nao mexia em nada do que ja
   estava no banco, e a tela ficava sem efeito visivel.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.domain import normalize_transaction_category
from apps.finance.models import (
    CategorizationRule,
    Transaction,
    TransactionType,
)

REAPPLY_URL = "/api/v1/categorization-rules/reapply/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_transaction(account, *, description, category="", provider_category="", external_id):
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description=description,
        amount=Decimal("25.00"),
        type=TransactionType.DEBIT,
        category=category,
        provider_category=provider_category,
        booked_at=timezone.now(),
    )


# --------------------------------------------------------------------------
# Precedencia
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_rule_wins_over_the_provider_category(user):
    """Regra explicita do usuario e o sinal mais forte que existe: se ela perde
    para o palpite do provedor, criar regra nao serve para nada."""
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    category = normalize_transaction_category(
        "UBER TRIP 123", provider_category="Travel", tx_type=TransactionType.DEBIT, user=user
    )

    assert category == "transporte"


@pytest.mark.django_db
def test_provider_category_is_used_when_no_rule_matches(user):
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    category = normalize_transaction_category(
        "PADARIA CENTRAL", provider_category="Food", tx_type=TransactionType.DEBIT, user=user
    )

    assert category == "Food"


@pytest.mark.django_db
def test_rule_priority_decides_between_two_matches(user):
    CategorizationRule.objects.create(
        user=user, pattern="mercado", category="generico", priority=200
    )
    CategorizationRule.objects.create(
        user=user, pattern="mercado livre", category="compras-online", priority=10
    )

    category = normalize_transaction_category(
        "MERCADO LIVRE PAGAMENTO", provider_category="", tx_type=TransactionType.DEBIT, user=user
    )

    assert category == "compras-online"


@pytest.mark.django_db
def test_inactive_rule_is_ignored(user):
    CategorizationRule.objects.create(
        user=user, pattern="uber", category="transporte", is_active=False
    )

    category = normalize_transaction_category(
        "UBER TRIP", provider_category="Travel", tx_type=TransactionType.DEBIT, user=user
    )

    # `provider_category` e traduzida para pt-BR (ver normalize_transaction_category):
    # "Travel" -> "Viagens". A regra inativa e ignorada; o teste verifica isso, nao a
    # lingua do fallback.
    assert category == "Viagens"


@pytest.mark.django_db
def test_another_users_rule_never_applies(user, other_user):
    CategorizationRule.objects.create(user=other_user, pattern="uber", category="do-invasor")

    category = normalize_transaction_category(
        "UBER TRIP", provider_category="", tx_type=TransactionType.DEBIT, user=user
    )

    assert category != "do-invasor"


# --------------------------------------------------------------------------
# Reaplicacao ao historico
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_reapply_recategorizes_existing_transactions(api, user, account):
    tx = make_transaction(
        account, description="UBER TRIP 99", category="expenses", external_id="tx-reapply-1"
    )
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    response = api.post(REAPPLY_URL)

    assert response.status_code == 200, response.data
    assert response.data["updated"] == 1
    tx.refresh_from_db()
    assert tx.category == "transporte"


@pytest.mark.django_db
def test_reapply_reports_zero_when_nothing_changes(api, user, account):
    make_transaction(
        account, description="UBER TRIP", category="transporte", external_id="tx-reapply-2"
    )
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    response = api.post(REAPPLY_URL)

    assert response.data["updated"] == 0


@pytest.mark.django_db
def test_reapply_never_touches_another_users_transactions(
    api, user, other_user, account, institution
):
    from apps.finance.models import Account, AccountType, Connection, ConnectionStatus

    other_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro-reapply",
        status=ConnectionStatus.ACTIVE,
    )
    other_account = Account.objects.create(
        connection=other_connection,
        external_id="acc-outro-reapply",
        name="Conta do outro",
        type=AccountType.CHECKING,
    )
    theirs = make_transaction(
        other_account, description="UBER TRIP", category="expenses", external_id="tx-outro-reapply"
    )
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    api.post(REAPPLY_URL)

    theirs.refresh_from_db()
    assert theirs.category == "expenses"


@pytest.mark.django_db
def test_reapply_covers_card_transactions(api, user, connection):
    from apps.finance.models import Card

    card = Card.objects.create(connection=connection, external_id="card-reapply", name="Cartao")
    tx = Transaction.objects.create(
        card=card,
        external_id="tx-card-reapply",
        description="UBER TRIP",
        amount=Decimal("30.00"),
        type=TransactionType.DEBIT,
        category="expenses",
        booked_at=timezone.now(),
    )
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    api.post(REAPPLY_URL)

    tx.refresh_from_db()
    assert tx.category == "transporte"


@pytest.mark.django_db
def test_reapply_cost_does_not_grow_per_transaction(api, user, account):
    """A reaplicacao le as regras uma vez e grava em lote. Uma query por transacao
    tornaria o botao inutilizavel em um historico real."""
    from django.db import connection as db_connection
    from django.test.utils import CaptureQueriesContext

    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")

    def count_queries_for(n: int) -> int:
        Transaction.objects.all().delete()
        for i in range(n):
            make_transaction(
                account,
                description="UBER TRIP",
                category="expenses",
                external_id=f"tx-cost-reapply-{i}",
            )
        with CaptureQueriesContext(db_connection) as ctx:
            api.post(REAPPLY_URL)
        return len(ctx)

    with_10 = count_queries_for(10)
    with_60 = count_queries_for(60)

    assert with_60 <= with_10 + 2, f"custo cresceu por transacao: {with_10} -> {with_60}"


@pytest.mark.django_db
def test_reapply_requires_authentication():
    response = APIClient().post(REAPPLY_URL)

    assert response.status_code in (401, 403)
