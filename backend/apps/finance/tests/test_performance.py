"""Testes de performance e paginacao.

Todos aqui travam custo, nao comportamento: sao os que quebram quando alguem
remove um `select_related` ou reintroduz uma chamada redundante. Contagem de query
e a unica forma de detectar isso -- N+1 nao muda a resposta, so a fatura.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection as db_connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.consolidation import (
    add_months,
    build_recent_month_averages,
    previous_month_keys,
)
from apps.finance.models import (
    Card,
    Investment,
    InvestmentPosition,
    SyncJob,
    Transaction,
    TransactionType,
)

# --------------------------------------------------------------------------
# Aritmetica de mes: pura, roda sem banco
# --------------------------------------------------------------------------


def test_previous_month_keys_walks_back_calendar_months():
    assert previous_month_keys(date(2026, 8, 15), 3) == [(2026, 7), (2026, 6), (2026, 5)]


def test_previous_month_keys_crosses_the_year():
    assert previous_month_keys(date(2026, 2, 10), 3) == [(2026, 1), (2025, 12), (2025, 11)]


def test_previous_month_keys_never_repeats_a_month_from_a_long_month():
    """`hoje - 30 dias` a partir de 31/03 cai em 01/03 -- o mesmo mes. A versao
    anterior usava essa aproximacao e podia contar marco duas vezes e pular
    fevereiro inteiro."""
    keys = previous_month_keys(date(2026, 3, 31), 3)

    assert keys == [(2026, 2), (2026, 1), (2025, 12)]
    assert len(set(keys)) == 3


def test_previous_month_keys_handles_january():
    assert previous_month_keys(date(2026, 1, 5), 2) == [(2025, 12), (2025, 11)]


def test_add_months_preserves_the_day_and_crosses_the_year():
    assert add_months(date(2026, 8, 15), 6) == date(2027, 2, 15)
    assert add_months(date(2026, 8, 15), 0) == date(2026, 8, 15)


def test_add_months_clamps_to_the_last_day_of_a_short_month():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 3, 31), 1) == date(2026, 4, 30)


def test_add_months_does_not_drift_like_the_30_day_approximation():
    """`data + timedelta(days=meses * 30)` erra cada vez mais conforme o horizonte
    cresce -- e a projecao de liberdade financeira usa horizontes longos. Em 120
    meses a aproximacao fica ~52 dias curta."""
    from datetime import timedelta

    start = date(2026, 1, 15)
    exact = add_months(start, 120)
    approximate = start + timedelta(days=120 * 30)

    assert exact == date(2036, 1, 15)
    assert (exact - approximate).days > 30, "a aproximacao ja deveria estar mais de um mes fora"


# --------------------------------------------------------------------------
# Medias mensais: uma passada, nao duas
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_recent_month_averages_reads_each_month_once(user, account):
    """A projecao de liberdade financeira calculava a media de poupanca e a de
    despesa em lacos separados sobre os mesmos meses: 6 chamadas de
    `build_monthly_cash_flow` onde 3 bastam."""
    with CaptureQueriesContext(db_connection) as ctx:
        build_recent_month_averages(user, months=3, today=date(2026, 8, 15))

    # 3 meses x 3 queries por mes (receita, despesa, assinaturas).
    assert len(ctx) <= 9, f"esperava no maximo 9 queries, foram {len(ctx)}"


@pytest.mark.django_db
def test_recent_month_averages_divides_by_the_number_of_months(user, account):
    for month in (5, 6, 7):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-avg-{month}",
            description="Salario",
            amount=Decimal("300.00"),
            type=TransactionType.CREDIT,
            booked_at=timezone.make_aware(timezone.datetime(2026, month, 10)),
        )

    averages = build_recent_month_averages(user, months=3, today=date(2026, 8, 15))

    assert averages["income"] == Decimal("300.00")


@pytest.mark.django_db
def test_recent_month_averages_with_no_data_returns_zeros(user):
    averages = build_recent_month_averages(user, months=3, today=date(2026, 8, 15))

    assert averages == {
        "income": Decimal("0"),
        "expenses": Decimal("0"),
        "savings": Decimal("0"),
    }


# --------------------------------------------------------------------------
# GraphQL: N+1
# --------------------------------------------------------------------------


def _execute(query, user):
    from django.test import RequestFactory

    from config.schema import schema

    request = RequestFactory().post("/graphql/")
    request.user = user
    result = schema.execute(query, context_value=request)
    assert not result.errors, result.errors
    return result.data


@pytest.mark.django_db
def test_investment_positions_do_not_trigger_one_query_per_position(user, connection):
    investment = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Tesouro", kind="fixed_income"
    )
    other = Investment.objects.create(
        connection=connection, external_id="inv-2", name="PETR4", kind="equity"
    )
    for i in range(10):
        InvestmentPosition.objects.create(
            investment=investment if i % 2 else other,
            as_of_date=date(2026, 8, i + 1),
            quantity=1,
            unit_price=10,
            market_value=10,
        )

    query = "{ investmentPositions { marketValue investment { id name } } }"
    with CaptureQueriesContext(db_connection) as ctx:
        data = _execute(query, user)

    assert len(data["investmentPositions"]) == 10
    assert len(ctx) <= 2, f"N+1 ao resolver investment: {len(ctx)} queries para 10 posicoes"


@pytest.mark.django_db
def test_financial_freedom_projection_does_not_read_months_twice(user, account):
    for month in (5, 6, 7):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-proj-{month}",
            description="Salario",
            amount=Decimal("5000.00"),
            type=TransactionType.CREDIT,
            booked_at=timezone.make_aware(timezone.datetime(2026, month, 10)),
        )

    query = """{
      financialFreedomProjection {
        currentNetWorth
        monthlySavings
        averageMonthlyExpenses
        monthsToFreedom
      }
    }"""
    with CaptureQueriesContext(db_connection) as ctx:
        data = _execute(query, user)

    assert data["financialFreedomProjection"] is not None
    # Antes: 6 chamadas de build_monthly_cash_flow (18 queries) + o resumo.
    assert len(ctx) <= 16, f"esperava no maximo 16 queries, foram {len(ctx)}"


@pytest.mark.django_db
def test_summary_is_computed_once_per_request(user, connection, account):
    """`financialSummary` e `financialFreedomProjection` recalculavam o resumo
    patrimonial cada um por conta -- o dashboard pede os dois na mesma query e
    iterava as contas duas vezes por carga de tela."""
    both = "{ financialSummary { netWorth } financialFreedomProjection { currentNetWorth } }"
    only_projection = "{ financialFreedomProjection { currentNetWorth } }"

    with CaptureQueriesContext(db_connection) as ctx_both:
        _execute(both, user)
    with CaptureQueriesContext(db_connection) as ctx_one:
        _execute(only_projection, user)

    # Pedir o resumo junto nao pode custar um recalculo inteiro a mais.
    assert len(ctx_both) == len(
        ctx_one
    ), f"resumo recalculado: {len(ctx_one)} query(s) sozinho, {len(ctx_both)} com o resumo"


# --------------------------------------------------------------------------
# REST: paginacao das colecoes que crescem sem limite
# --------------------------------------------------------------------------


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_transactions_are_paginated(api, account):
    for i in range(120):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-page-{i}",
            description=f"Compra {i}",
            amount=Decimal("10.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.now(),
        )

    response = api.get("/api/v1/transactions/")

    assert response.status_code == 200
    assert response.data["count"] == 120
    assert len(response.data["results"]) == 100
    assert response.data["next"] is not None


@pytest.mark.django_db
def test_transaction_page_size_is_capped(api, account):
    """Sem teto, `?page_size=999999` derrota a paginacao."""
    for i in range(10):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-cap-{i}",
            description="Compra",
            amount=Decimal("10.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.now(),
        )

    response = api.get("/api/v1/transactions/?page_size=999999")

    from apps.finance.pagination import UnboundedCollectionPagination

    assert response.status_code == 200
    assert len(response.data["results"]) <= UnboundedCollectionPagination.max_page_size


@pytest.mark.django_db
def test_transaction_list_cost_does_not_grow_with_volume(api, account):
    def count_queries_for(n: int) -> int:
        Transaction.objects.all().delete()
        for i in range(n):
            Transaction.objects.create(
                account=account,
                external_id=f"tx-cost-{i}",
                description="Compra",
                amount=Decimal("10.00"),
                type=TransactionType.DEBIT,
                booked_at=timezone.now(),
            )
        with CaptureQueriesContext(db_connection) as ctx:
            api.get("/api/v1/transactions/")
        return len(ctx)

    with_5 = count_queries_for(5)
    with_50 = count_queries_for(50)

    assert with_5 == with_50, f"N+1 na serializacao: {with_5} -> {with_50}"


@pytest.mark.django_db
def test_sync_jobs_are_paginated_and_do_not_n_plus_one_on_institution(api, connection):
    """`SyncJobSerializer` expoe `connection.institution.name`. Com
    `select_related` so ate `connection`, cada job buscava a instituicao de novo."""
    for _ in range(30):
        SyncJob.objects.create(connection=connection, kind="full")

    with CaptureQueriesContext(db_connection) as ctx:
        response = api.get("/api/v1/sync-jobs/")

    assert response.status_code == 200
    assert response.data["count"] == 30
    assert len(ctx) <= 3, f"N+1 ao resolver institution: {len(ctx)} queries para 30 jobs"


@pytest.mark.django_db
def test_small_collections_stay_unpaginated(api, connection, account):
    """Contas, cartoes e afins tem tamanho naturalmente pequeno. Paginar mudaria a
    forma da resposta em varias telas sem ganho nenhum."""
    Card.objects.create(connection=connection, external_id="card-1", name="Cartao")

    for path in ("/api/v1/accounts/", "/api/v1/cards/", "/api/v1/connections/"):
        response = api.get(path)
        assert response.status_code == 200
        assert isinstance(response.data, list), f"{path} passou a vir paginado"
