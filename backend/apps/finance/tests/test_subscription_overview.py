"""Testes de build_subscription_overview.

A visao de assinaturas do dashboard precisa responder tres coisas que hoje ninguem
calcula: quanto compromete por mes, o que esta atrasado e o que vence em seguida.

Todos os testes passam `today` explicito: a funcao decide janela de mes e horizonte
a partir da data, e depender do dia real deixaria a suite intermitente (o teste de
"vence nos proximos 30 dias" quebraria perto da virada do mes).
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.finance.consolidation import build_subscription_overview
from apps.finance.models import (
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
)

TODAY = date(2026, 8, 15)


def make_subscription(user, *, name, amount, due_day=10, is_active=True, category=None):
    return Subscription.objects.create(
        user=user,
        name=name,
        category=category or SubscriptionCategory.OTHER,
        amount=Decimal(amount),
        due_day=due_day,
        is_active=is_active,
    )


@pytest.mark.django_db
def test_empty_state_returns_zeros_not_none(user):
    overview = build_subscription_overview(user, today=TODAY)

    assert overview["monthly_recurring_total"] == Decimal("0")
    assert overview["active_count"] == 0
    assert overview["overdue_total"] == Decimal("0")
    assert overview["overdue"] == []
    assert overview["upcoming"] == []


@pytest.mark.django_db
def test_monthly_recurring_total_sums_only_active_subscriptions(user):
    make_subscription(user, name="Internet", amount="120.00")
    make_subscription(user, name="Streaming", amount="55.50")
    make_subscription(user, name="Cancelada", amount="999.00", is_active=False)

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["monthly_recurring_total"] == Decimal("175.50")
    assert overview["active_count"] == 2


@pytest.mark.django_db
def test_overdue_lists_payments_oldest_first_with_expected_amount(user):
    agua = make_subscription(user, name="Conta de agua", amount="90.00")
    luz = make_subscription(user, name="Conta de luz", amount="210.00")
    SubscriptionPayment.objects.create(
        subscription=luz, due_date=date(2026, 7, 10), status=SubscriptionStatus.OVERDUE
    )
    SubscriptionPayment.objects.create(
        subscription=agua, due_date=date(2026, 6, 10), status=SubscriptionStatus.OVERDUE
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert [(item["name"], item["due_date"], item["amount"]) for item in overview["overdue"]] == [
        ("Conta de agua", date(2026, 6, 10), Decimal("90.00")),
        ("Conta de luz", date(2026, 7, 10), Decimal("210.00")),
    ]
    assert overview["overdue_total"] == Decimal("300.00")


@pytest.mark.django_db
def test_upcoming_covers_the_horizon_and_excludes_what_falls_outside(user):
    sub = make_subscription(user, name="Internet", amount="120.00")
    for due in (
        date(2026, 8, 10),  # ja passou
        date(2026, 8, 20),  # dentro do horizonte
        date(2026, 9, 10),  # dentro do horizonte
        date(2026, 10, 10),  # alem dos 30 dias
    ):
        SubscriptionPayment.objects.create(
            subscription=sub, due_date=due, status=SubscriptionStatus.PENDING
        )

    overview = build_subscription_overview(user, today=TODAY, upcoming_days=30)

    assert [item["due_date"] for item in overview["upcoming"]] == [
        date(2026, 8, 20),
        date(2026, 9, 10),
    ]


@pytest.mark.django_db
def test_upcoming_ignores_payments_already_paid(user):
    sub = make_subscription(user, name="Internet", amount="120.00")
    SubscriptionPayment.objects.create(
        subscription=sub,
        due_date=date(2026, 8, 20),
        status=SubscriptionStatus.PAID,
        paid_date=date(2026, 8, 14),
        paid_amount=Decimal("120.00"),
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["upcoming"] == []


@pytest.mark.django_db
def test_paid_this_month_uses_the_amount_actually_paid(user):
    """O valor pago pode divergir do esperado (reajuste, consumo variavel). O mes
    fechado precisa refletir o que saiu da conta, nao o valor cadastrado."""
    sub = make_subscription(user, name="Conta de luz", amount="200.00")
    SubscriptionPayment.objects.create(
        subscription=sub,
        due_date=date(2026, 8, 10),
        status=SubscriptionStatus.PAID,
        paid_date=date(2026, 8, 11),
        paid_amount=Decimal("243.71"),
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["paid_this_month"] == Decimal("243.71")


@pytest.mark.django_db
def test_paid_without_amount_falls_back_to_the_expected_value(user):
    """Marcacao manual de pago nao exige informar valor."""
    sub = make_subscription(user, name="Internet", amount="120.00")
    SubscriptionPayment.objects.create(
        subscription=sub,
        due_date=date(2026, 8, 10),
        status=SubscriptionStatus.PAID,
        paid_date=date(2026, 8, 10),
        paid_amount=None,
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["paid_this_month"] == Decimal("120.00")


@pytest.mark.django_db
def test_pending_this_month_counts_pending_and_overdue_of_the_month(user):
    internet = make_subscription(user, name="Internet", amount="120.00")
    agua = make_subscription(user, name="Conta de agua", amount="90.00")
    SubscriptionPayment.objects.create(
        subscription=internet, due_date=date(2026, 8, 20), status=SubscriptionStatus.PENDING
    )
    SubscriptionPayment.objects.create(
        subscription=agua, due_date=date(2026, 8, 5), status=SubscriptionStatus.OVERDUE
    )
    # Mes seguinte nao entra no fechamento do mes corrente.
    SubscriptionPayment.objects.create(
        subscription=internet, due_date=date(2026, 9, 20), status=SubscriptionStatus.PENDING
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["pending_this_month"] == Decimal("210.00")


@pytest.mark.django_db
def test_december_does_not_leak_into_the_next_year(user):
    """A janela do mes vira o ano; um `month + 1` ingenuo estouraria em dezembro."""
    sub = make_subscription(user, name="Internet", amount="120.00")
    SubscriptionPayment.objects.create(
        subscription=sub, due_date=date(2026, 12, 20), status=SubscriptionStatus.PENDING
    )
    SubscriptionPayment.objects.create(
        subscription=sub, due_date=date(2027, 1, 20), status=SubscriptionStatus.PENDING
    )

    overview = build_subscription_overview(user, today=date(2026, 12, 1))

    assert overview["pending_this_month"] == Decimal("120.00")


@pytest.mark.django_db
def test_everything_is_scoped_to_the_user(user, other_user):
    mine = make_subscription(user, name="Minha internet", amount="120.00")
    theirs = make_subscription(other_user, name="Internet do invasor", amount="500.00")
    SubscriptionPayment.objects.create(
        subscription=mine, due_date=date(2026, 8, 20), status=SubscriptionStatus.PENDING
    )
    SubscriptionPayment.objects.create(
        subscription=theirs, due_date=date(2026, 8, 21), status=SubscriptionStatus.PENDING
    )
    SubscriptionPayment.objects.create(
        subscription=theirs, due_date=date(2026, 7, 21), status=SubscriptionStatus.OVERDUE
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["monthly_recurring_total"] == Decimal("120.00")
    assert [item["name"] for item in overview["upcoming"]] == ["Minha internet"]
    assert overview["overdue"] == []


@pytest.mark.django_db
def test_inactive_subscription_payments_do_not_nag(user):
    """Assinatura cancelada nao deve continuar cobrando atencao no dashboard."""
    cancelada = make_subscription(user, name="Cancelada", amount="80.00", is_active=False)
    SubscriptionPayment.objects.create(
        subscription=cancelada, due_date=date(2026, 7, 10), status=SubscriptionStatus.OVERDUE
    )

    overview = build_subscription_overview(user, today=TODAY)

    assert overview["overdue"] == []
    assert overview["overdue_total"] == Decimal("0")


@pytest.mark.django_db
def test_cost_does_not_grow_with_the_number_of_subscriptions(user):
    """A view roda a cada carga do dashboard: o custo precisa ser fixo, nao uma
    query por assinatura."""
    from django.db import connection as db_connection
    from django.test.utils import CaptureQueriesContext

    def count_queries_for(n: int) -> int:
        Subscription.objects.filter(user=user).delete()
        for i in range(n):
            sub = make_subscription(user, name=f"Servico {i}", amount="10.00")
            SubscriptionPayment.objects.create(
                subscription=sub, due_date=date(2026, 8, 20), status=SubscriptionStatus.PENDING
            )
        with CaptureQueriesContext(db_connection) as ctx:
            build_subscription_overview(user, today=TODAY)
        return len(ctx)

    with_5 = count_queries_for(5)
    with_30 = count_queries_for(30)

    assert with_5 == with_30, f"custo cresceu com o numero de assinaturas: {with_5} -> {with_30}"
