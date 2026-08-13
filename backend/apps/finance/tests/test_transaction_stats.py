"""Testes do endpoint de estatisticas da tela de transacoes.

Usa o mesmo `filter_transactions` da listagem/exportacao (`test_transaction_
filters.py`), entao os testes aqui focam nos totais e na exclusao de
transferencias internas -- nao repetem cada filtro individual, ja cobertos lá.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.models import Transaction, TransactionType

STATS_URL = "/api/v1/transactions/stats/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def dataset(db, account, card):
    rows = [
        ("tx-1", "Salario mensal", "5000.00", TransactionType.CREDIT, "Income", "", 5),
        ("tx-2", "UBER TRIP centro", "25.00", TransactionType.DEBIT, "Transportation", "", 6),
        ("tx-3", "MERCADO do bairro", "150.00", TransactionType.DEBIT, "Groceries", "", 10),
        ("tx-4", "UBER EATS pedido", "75.00", TransactionType.DEBIT, "Groceries", "", 20),
        # Pagamento de fatura: credito no cartao, categoria de transferencia interna
        # -- deve ficar fora dos totais e das categorias.
        ("tx-5", "Pagamento de fatura", "250.00", TransactionType.CREDIT, "Transfer", "Credit Card Payment", 21),
    ]
    for external_id, description, amount, tx_type, category, provider_category, day in rows:
        Transaction.objects.create(
            account=account,
            external_id=external_id,
            description=description,
            amount=Decimal(amount),
            type=tx_type,
            category=category,
            provider_category=provider_category,
            booked_at=timezone.make_aware(timezone.datetime(2026, 8, day, 12, 0)),
        )
    return {"account": account, "card": card}


@pytest.fixture
def card(connection):
    from apps.finance.models import Card

    return Card.objects.create(connection=connection, external_id="card-stats", name="Cartao")


@pytest.mark.django_db
def test_totals_income_expenses_and_balance(api, dataset):
    data = api.get(STATS_URL).data

    assert Decimal(data["total_income"]) == Decimal("5000.00")
    assert Decimal(data["total_expenses"]) == Decimal("250.00")
    assert Decimal(data["balance"]) == Decimal("4750.00")


@pytest.mark.django_db
def test_internal_transfers_are_excluded_from_totals_and_categories(api, dataset):
    data = api.get(STATS_URL).data

    categories = {row["category"] for row in data["income_categories"]}
    assert "Transfer" not in categories
    assert Decimal(data["total_income"]) == Decimal("5000.00")


@pytest.mark.django_db
def test_transaction_count_includes_everything_in_the_filtered_set(api, dataset):
    """O contador bate com o total da tela (`count`), inclusive transferencias
    internas -- so os agregados de receita/despesa/categoria as excluem."""
    data = api.get(STATS_URL).data

    assert data["transaction_count"] == 5


@pytest.mark.django_db
def test_average_expense_is_the_mean_of_debit_transactions(api, dataset):
    data = api.get(STATS_URL).data

    # (25 + 150 + 75) / 3
    assert Decimal(data["average_expense"]) == Decimal("83.33")


@pytest.mark.django_db
def test_expense_categories_are_grouped_and_sorted_by_total(api, dataset):
    data = api.get(STATS_URL).data

    by_category = {row["category"]: row for row in data["expense_categories"]}
    assert Decimal(by_category["Groceries"]["total"]) == Decimal("225.00")
    assert by_category["Groceries"]["count"] == 2
    assert Decimal(by_category["Transportation"]["total"]) == Decimal("25.00")
    # Maior total primeiro.
    assert [row["category"] for row in data["expense_categories"]] == ["Groceries", "Transportation"]


@pytest.mark.django_db
def test_expense_category_percentages_sum_to_one_hundred(api, dataset):
    data = api.get(STATS_URL).data

    total_percentage = sum(Decimal(row["percentage"]) for row in data["expense_categories"])
    assert total_percentage == Decimal("100.00")


@pytest.mark.django_db
def test_stats_respect_the_same_filters_as_the_list(api, dataset):
    data = api.get(f"{STATS_URL}?category=Groceries").data

    assert Decimal(data["total_expenses"]) == Decimal("225.00")
    assert [row["category"] for row in data["expense_categories"]] == ["Groceries"]


@pytest.mark.django_db
def test_stats_never_cross_users(api, other_user, dataset, institution):
    from apps.finance.models import Account, AccountType, Connection, ConnectionStatus

    other_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro-stats",
        status=ConnectionStatus.ACTIVE,
    )
    other_account = Account.objects.create(
        connection=other_connection,
        external_id="acc-outro-stats",
        name="Conta do outro",
        type=AccountType.CHECKING,
    )
    Transaction.objects.create(
        account=other_account,
        external_id="tx-outro-stats",
        description="Salario do invasor",
        amount=Decimal("9999.00"),
        type=TransactionType.CREDIT,
        category="Income",
        booked_at=timezone.now(),
    )

    data = api.get(STATS_URL).data
    assert Decimal(data["total_income"]) == Decimal("5000.00")


@pytest.mark.django_db
def test_stats_with_no_transactions_returns_zeroed_totals(api, db, user):
    data = api.get(STATS_URL).data

    assert Decimal(data["total_income"]) == Decimal("0.00")
    assert Decimal(data["total_expenses"]) == Decimal("0.00")
    assert Decimal(data["average_expense"]) == Decimal("0.00")
    assert data["expense_categories"] == []
    assert data["transaction_count"] == 0
