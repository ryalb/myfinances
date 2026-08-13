"""Testes do schema GraphQL.

Cinco resolvers (subscriptions, subscriptionPayments, categorizationRules,
pensionPlans, investmentPositions) existiam em graphql.py sem o campo
correspondente declarado na classe Query. Em graphene um resolver sem campo e
silenciosamente ignorado: nao ha erro de import, nem de execucao -- o campo
simplesmente nao entra no schema e a query falha no cliente.

O primeiro teste trava a lista de campos expostos justamente porque esse modo de
falha e invisivel.
"""

import pytest
from django.test import RequestFactory

from apps.finance.models import (
    CategorizationRule,
    Investment,
    InvestmentPosition,
    PensionPlan,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
)
from config.schema import schema

EXPECTED_QUERY_FIELDS = {
    "institutions",
    "accounts",
    "netWorthHistory",
    "financialSummary",
    "monthlyCashFlow",
    "investmentDistribution",
    "financialFreedomProjection",
    "subscriptions",
    "subscriptionPayments",
    "categorizationRules",
    "pensionPlans",
    "investmentPositions",
    "subscriptionOverview",
    "alerts",
    "futureProjection",
    "financialHealthScore",
    "portfolioAllocationDrift",
    "untaggedInvestments",
    "taggableCashAccounts",
    "budgetBucketDrift",
}


def execute(query, user=None, **variables):
    request = RequestFactory().post("/graphql/")
    request.user = user
    result = schema.execute(query, context_value=request, variable_values=variables or None)
    assert not result.errors, result.errors
    return result.data


def test_query_exposes_every_declared_resolver():
    exposed = set(schema.graphql_schema.query_type.fields)

    assert exposed == EXPECTED_QUERY_FIELDS, (
        f"faltando no schema: {EXPECTED_QUERY_FIELDS - exposed}; "
        f"nao esperado: {exposed - EXPECTED_QUERY_FIELDS}"
    )


@pytest.fixture
def subscription(db, user):
    return Subscription.objects.create(
        user=user,
        name="Netflix",
        category=SubscriptionCategory.STREAMING,
        amount=55,
        due_day=10,
    )


@pytest.fixture
def other_subscription(db, other_user):
    return Subscription.objects.create(
        user=other_user,
        name="Spotify do invasor",
        category=SubscriptionCategory.STREAMING,
        amount=22,
        due_day=15,
    )


@pytest.mark.django_db
def test_subscriptions_returns_only_the_authenticated_users_rows(
    user, subscription, other_subscription
):
    data = execute("{ subscriptions { name } }", user=user)

    assert [row["name"] for row in data["subscriptions"]] == ["Netflix"]


@pytest.mark.django_db
def test_subscription_payments_are_scoped_to_the_user(user, subscription, other_subscription):
    SubscriptionPayment.objects.create(subscription=subscription, due_date="2026-08-10")
    SubscriptionPayment.objects.create(subscription=other_subscription, due_date="2026-08-15")

    data = execute("{ subscriptionPayments { dueDate } }", user=user)

    assert [row["dueDate"] for row in data["subscriptionPayments"]] == ["2026-08-10"]


@pytest.mark.django_db
def test_subscription_payments_can_be_filtered_by_subscription(user, subscription):
    other_own = Subscription.objects.create(
        user=user,
        name="Internet",
        category=SubscriptionCategory.INTERNET,
        amount=100,
        due_day=20,
    )
    SubscriptionPayment.objects.create(subscription=subscription, due_date="2026-08-10")
    SubscriptionPayment.objects.create(subscription=other_own, due_date="2026-08-20")

    data = execute(
        "query ($id: Int) { subscriptionPayments(subscriptionId: $id) { dueDate } }",
        user=user,
        id=subscription.id,
    )

    assert [row["dueDate"] for row in data["subscriptionPayments"]] == ["2026-08-10"]


@pytest.mark.django_db
def test_categorization_rules_are_scoped_to_the_user(user, other_user):
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")
    CategorizationRule.objects.create(user=other_user, pattern="ifood", category="alimentacao")

    data = execute("{ categorizationRules { pattern } }", user=user)

    assert [row["pattern"] for row in data["categorizationRules"]] == ["uber"]


@pytest.mark.django_db
def test_pension_plans_are_scoped_to_the_user(user, other_user, connection, institution):
    from apps.finance.models import Connection, ConnectionStatus

    PensionPlan.objects.create(
        connection=connection, user=user, external_id="prev-1", name="PGBL", provider="Banco Teste"
    )
    other_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro-prev",
        status=ConnectionStatus.ACTIVE,
    )
    PensionPlan.objects.create(
        connection=other_connection,
        user=other_user,
        external_id="prev-2",
        name="VGBL do invasor",
        provider="Outro",
    )

    data = execute("{ pensionPlans { name } }", user=user)

    assert [row["name"] for row in data["pensionPlans"]] == ["PGBL"]


@pytest.mark.django_db
def test_investment_positions_are_scoped_and_filterable(user, connection):
    tesouro = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Tesouro Selic", kind="fixed_income"
    )
    acao = Investment.objects.create(
        connection=connection, external_id="inv-2", name="PETR4", kind="equity"
    )
    InvestmentPosition.objects.create(
        investment=tesouro, as_of_date="2026-08-01", quantity=1, unit_price=100, market_value=100
    )
    InvestmentPosition.objects.create(
        investment=acao, as_of_date="2026-08-02", quantity=10, unit_price=30, market_value=300
    )

    every = execute("{ investmentPositions { marketValue } }", user=user)
    assert len(every["investmentPositions"]) == 2

    filtered = execute(
        "query ($id: Int) { investmentPositions(investmentId: $id) { marketValue } }",
        user=user,
        id=tesouro.id,
    )
    assert [row["marketValue"] for row in filtered["investmentPositions"]] == [100.0]


@pytest.mark.django_db
def test_subscription_overview_serializes_dates_and_decimals(user, subscription):
    """A agregacao devolve `date` e `Decimal`; o resolver precisa converter, ou o
    graphene serializa como string do repr (`Decimal('55.00')`)."""
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date="2026-07-10",
        status=SubscriptionStatus.OVERDUE,
    )

    data = execute(
        """{
          subscriptionOverview {
            monthlyRecurringTotal
            activeCount
            overdueTotal
            overdue { name dueDate amount status }
          }
        }""",
        user=user,
    )

    overview = data["subscriptionOverview"]
    assert overview["monthlyRecurringTotal"] == 55.0
    assert overview["activeCount"] == 1
    assert overview["overdueTotal"] == 55.0
    assert overview["overdue"] == [
        {"name": "Netflix", "dueDate": "2026-07-10", "amount": 55.0, "status": "overdue"}
    ]


@pytest.mark.django_db
def test_subscription_overview_is_scoped_to_the_user(user, subscription, other_subscription):
    data = execute("{ subscriptionOverview { monthlyRecurringTotal } }", user=user)

    assert data["subscriptionOverview"]["monthlyRecurringTotal"] == 55.0


@pytest.mark.django_db
def test_subscription_overview_returns_null_for_anonymous(subscription):
    from django.contrib.auth.models import AnonymousUser

    data = execute("{ subscriptionOverview { monthlyRecurringTotal } }", user=AnonymousUser())

    assert data["subscriptionOverview"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "{ subscriptions { name } }",
        "{ subscriptionPayments { dueDate } }",
        "{ categorizationRules { pattern } }",
        "{ pensionPlans { name } }",
        "{ investmentPositions { marketValue } }",
    ],
)
def test_anonymous_access_returns_nothing(query, subscription):
    from django.contrib.auth.models import AnonymousUser

    data = execute(query, user=AnonymousUser())

    assert data[next(iter(data))] == []
