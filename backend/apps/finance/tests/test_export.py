"""Testes da exportacao CSV.

Duas coisas justificam os testes serem sobre o conteudo e nao so o status: o
arquivo e o produto (vai para planilha e declaracao), e o endpoint le dado
financeiro de todo mundo se o escopo por usuario falhar.
"""

import csv
import io
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.models import (
    Account,
    AccountType,
    Connection,
    ConnectionStatus,
    FinancialInstitution,
    Transaction,
    TransactionType,
)

URL = "/api/v1/export/transactions.csv"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def read_csv(response) -> list[dict]:
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(body)))


@pytest.fixture
def transaction(db, account):
    return Transaction.objects.create(
        account=account,
        external_id="tx-export-1",
        description="Mercado do bairro",
        amount=Decimal("123.45"),
        currency="BRL",
        type=TransactionType.DEBIT,
        category="alimentacao",
        booked_at=timezone.make_aware(timezone.datetime(2026, 8, 10, 14, 30)),
    )


@pytest.mark.django_db
def test_export_returns_a_csv_attachment(api, transaction):
    response = api.get(URL)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    assert ".csv" in response["Content-Disposition"]


@pytest.mark.django_db
def test_export_carries_the_transaction_fields(api, transaction, account):
    rows = read_csv(api.get(URL))

    assert len(rows) == 1
    row = rows[0]
    assert row["data"] == "2026-08-10"
    assert row["descricao"] == "Mercado do bairro"
    assert row["valor"] == "123.45"
    assert row["tipo"] == "despesa"
    assert row["categoria"] == "alimentacao"
    assert row["conta"] == account.name
    assert row["instituicao"] == account.connection.institution.name


@pytest.mark.django_db
def test_export_uses_a_decimal_point_not_the_django_locale(api, transaction):
    """`LANGUAGE_CODE = pt-br` faz o Django formatar decimal com virgula. Numa
    coluna CSV isso vira texto na planilha, ou pior, muda a ordem de grandeza."""
    rows = read_csv(api.get(URL))

    assert rows[0]["valor"] == "123.45"
    assert "," not in rows[0]["valor"]


@pytest.mark.django_db
def test_export_never_leaks_another_users_transactions(api, transaction, other_user):
    institution = FinancialInstitution.objects.create(name="Outro banco", provider_id="999")
    other_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro-export",
        status=ConnectionStatus.ACTIVE,
    )
    other_account = Account.objects.create(
        connection=other_connection,
        external_id="acc-outro-export",
        name="Conta do outro",
        type=AccountType.CHECKING,
    )
    Transaction.objects.create(
        account=other_account,
        external_id="tx-outro-export",
        description="Segredo do outro",
        amount=Decimal("999.00"),
        type=TransactionType.DEBIT,
        booked_at=timezone.now(),
    )

    rows = read_csv(api.get(URL))

    assert [row["descricao"] for row in rows] == ["Mercado do bairro"]


@pytest.mark.django_db
def test_export_respects_the_date_range(api, account):
    for day in (5, 15, 25):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-range-{day}",
            description=f"Compra {day}",
            amount=Decimal("10.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.make_aware(timezone.datetime(2026, 8, day)),
        )

    rows = read_csv(api.get(f"{URL}?start_date=2026-08-10&end_date=2026-08-20"))

    assert [row["descricao"] for row in rows] == ["Compra 15"]


@pytest.mark.django_db
def test_export_is_not_paginated(api, account):
    """A paginacao das transacoes nao pode vazar para o export: um CSV com 100
    linhas de um historico de milhares e uma armadilha silenciosa."""
    for i in range(150):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-full-{i}",
            description=f"Compra {i}",
            amount=Decimal("10.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.now(),
        )

    rows = read_csv(api.get(URL))

    assert len(rows) == 150


@pytest.mark.django_db
def test_export_with_no_transactions_still_returns_the_header(api):
    """Arquivo vazio de verdade parece download corrompido."""
    response = api.get(URL)
    body = b"".join(response.streaming_content).decode("utf-8-sig")

    assert response.status_code == 200
    assert body.strip().startswith("data,")


@pytest.mark.django_db
def test_export_requires_authentication():
    response = APIClient().get(URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_card_transactions_are_included(api, connection):
    from apps.finance.models import Card

    card = Card.objects.create(connection=connection, external_id="card-export", name="Cartao Visa")
    Transaction.objects.create(
        card=card,
        external_id="tx-card-export",
        description="Compra no cartao",
        amount=Decimal("50.00"),
        type=TransactionType.DEBIT,
        booked_at=timezone.now(),
    )

    rows = read_csv(api.get(URL))

    assert len(rows) == 1
    assert rows[0]["conta"] == "Cartao Visa"
