"""Testes dos filtros de transacoes.

O helper e compartilhado entre a listagem e a exportacao CSV, entao os testes cobrem
os dois caminhos: um filtro que vale so na tela produziria um CSV que nao corresponde
ao que o usuario esta vendo.
"""

import csv
import io
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.models import Card, Transaction, TransactionType

LIST_URL = "/api/v1/transactions/"
EXPORT_URL = "/api/v1/export/transactions.csv"
CATEGORIES_URL = "/api/v1/transactions/categories/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def dataset(db, connection, account):
    card = Card.objects.create(connection=connection, external_id="card-f", name="Cartao")
    rows = [
        ("tx-1", "UBER TRIP centro", "25.00", TransactionType.DEBIT, "Transportation", 3, account),
        ("tx-2", "MERCADO do bairro", "150.00", TransactionType.DEBIT, "Groceries", 10, account),
        ("tx-3", "Salario mensal", "5000.00", TransactionType.CREDIT, "Income", 5, account),
        ("tx-4", "UBER EATS pedido", "80.00", TransactionType.DEBIT, "Food delivery", 20, card),
    ]
    for external_id, description, amount, tx_type, category, day, holder in rows:
        Transaction.objects.create(
            account=holder if holder is account else None,
            card=holder if holder is card else None,
            external_id=external_id,
            description=description,
            amount=Decimal(amount),
            type=tx_type,
            category=category,
            booked_at=timezone.make_aware(timezone.datetime(2026, 8, day, 12, 0)),
        )
    return {"card": card, "account": account}


def descriptions(response) -> set[str]:
    return {row["description"] for row in response.data["results"]}


def exported(response) -> set[str]:
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    return {row["descricao"] for row in csv.DictReader(io.StringIO(body))}


# --------------------------------------------------------------------------
# Listagem
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_matches_the_description_case_insensitively(api, dataset):
    response = api.get(f"{LIST_URL}?search=uber")

    assert descriptions(response) == {"UBER TRIP centro", "UBER EATS pedido"}


@pytest.mark.django_db
def test_search_ignores_surrounding_whitespace(api, dataset):
    assert descriptions(api.get(f"{LIST_URL}?search=  mercado  ")) == {"MERCADO do bairro"}


@pytest.mark.django_db
def test_blank_search_does_not_filter(api, dataset):
    assert len(api.get(f"{LIST_URL}?search=").data["results"]) == 4


@pytest.mark.django_db
def test_category_filter_is_exact_not_partial(api, dataset):
    """A lista do filtro vem de valores existentes, entao "Groceries" nao deve
    arrastar uma categoria que apenas contenha essa palavra."""
    Transaction.objects.create(
        account=dataset["account"],
        external_id="tx-5",
        description="Outra coisa",
        amount=Decimal("10.00"),
        type=TransactionType.DEBIT,
        category="Groceries delivery",
        booked_at=timezone.now(),
    )

    assert descriptions(api.get(f"{LIST_URL}?category=Groceries")) == {"MERCADO do bairro"}


@pytest.mark.django_db
def test_type_filter(api, dataset):
    assert descriptions(api.get(f"{LIST_URL}?type=credit")) == {"Salario mensal"}
    assert len(api.get(f"{LIST_URL}?type=debit").data["results"]) == 3


@pytest.mark.django_db
def test_invalid_type_is_ignored_instead_of_erroring(api, dataset):
    """Filtro escrito errado na URL nao deve derrubar a tela."""
    response = api.get(f"{LIST_URL}?type=qualquer")

    assert response.status_code == 200
    assert len(response.data["results"]) == 4


@pytest.mark.django_db
def test_account_and_card_filters(api, dataset):
    by_card = api.get(f"{LIST_URL}?card={dataset['card'].id}")
    assert descriptions(by_card) == {"UBER EATS pedido"}

    by_account = api.get(f"{LIST_URL}?account={dataset['account'].id}")
    assert "UBER EATS pedido" not in descriptions(by_account)


@pytest.mark.django_db
def test_amount_range(api, dataset):
    response = api.get(f"{LIST_URL}?min_amount=50&max_amount=200")

    assert descriptions(response) == {"MERCADO do bairro", "UBER EATS pedido"}


@pytest.mark.django_db
def test_non_numeric_amount_is_ignored(api, dataset):
    response = api.get(f"{LIST_URL}?min_amount=abc")

    assert response.status_code == 200
    assert len(response.data["results"]) == 4


@pytest.mark.django_db
def test_date_range_still_works(api, dataset):
    response = api.get(f"{LIST_URL}?start_date=2026-08-04&end_date=2026-08-11")

    assert descriptions(response) == {"Salario mensal", "MERCADO do bairro"}


@pytest.mark.django_db
def test_filters_combine(api, dataset):
    response = api.get(f"{LIST_URL}?search=uber&type=debit&max_amount=50")

    assert descriptions(response) == {"UBER TRIP centro"}


@pytest.mark.django_db
def test_filters_never_cross_users(api, other_user, dataset, institution):
    from apps.finance.models import Account, AccountType, Connection, ConnectionStatus

    other_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro-filtro",
        status=ConnectionStatus.ACTIVE,
    )
    other_account = Account.objects.create(
        connection=other_connection,
        external_id="acc-outro-filtro",
        name="Conta do outro",
        type=AccountType.CHECKING,
    )
    Transaction.objects.create(
        account=other_account,
        external_id="tx-outro-filtro",
        description="UBER do invasor",
        amount=Decimal("30.00"),
        type=TransactionType.DEBIT,
        booked_at=timezone.now(),
    )

    assert "UBER do invasor" not in descriptions(api.get(f"{LIST_URL}?search=uber"))


@pytest.mark.django_db
def test_newest_first(api, dataset):
    dates = [row["booked_at"] for row in api.get(LIST_URL).data["results"]]

    assert dates == sorted(dates, reverse=True)


# --------------------------------------------------------------------------
# Lista de categorias para o filtro
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_categories_are_distinct_sorted_and_scoped(api, dataset):
    response = api.get(CATEGORIES_URL)

    assert response.status_code == 200
    assert response.data == ["Food delivery", "Groceries", "Income", "Transportation"]


@pytest.mark.django_db
def test_categories_skip_the_empty_string(api, account):
    Transaction.objects.create(
        account=account,
        external_id="tx-sem-cat",
        description="Sem categoria",
        amount=Decimal("10.00"),
        type=TransactionType.DEBIT,
        category="",
        booked_at=timezone.now(),
    )

    assert api.get(CATEGORIES_URL).data == []


# --------------------------------------------------------------------------
# Exportacao usa os mesmos filtros
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_export_applies_the_same_filters_as_the_list(api, dataset):
    """Se a exportacao ignorar os filtros, o CSV nao corresponde a tela."""
    response = api.get(f"{EXPORT_URL}?search=uber&type=debit")

    assert exported(response) == {"UBER TRIP centro", "UBER EATS pedido"}


@pytest.mark.django_db
def test_export_respects_the_category_filter(api, dataset):
    assert exported(api.get(f"{EXPORT_URL}?category=Income")) == {"Salario mensal"}


@pytest.mark.django_db
def test_export_without_filters_returns_everything(api, dataset):
    assert len(exported(api.get(EXPORT_URL))) == 4
