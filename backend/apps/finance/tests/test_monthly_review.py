"""Testes do ritual mensal de revisao financeira.

`build_monthly_review_summary` e o unico jeito de acessar/criar um
`MonthlyReview`: a linha nasce vazia no primeiro GET/PATCH do mes (mesmo idiom
de `snapshot_net_worth`), e tudo que nao e input do usuario (variacao de
patrimonio, tendencia de poupanca, deltas de categoria, conquistas) e sempre
recalculado das tabelas fonte, nunca lido de volta do model.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.consolidation import (
    build_category_deltas_for_month,
    build_monthly_review_summary,
    build_savings_rate_trend,
)
from apps.finance.models import (
    FinancialGoal,
    GoalStatus,
    MonthlyReview,
    NetWorthSnapshot,
    Transaction,
    TransactionType,
)

URL = "/api/v1/monthly-review/"


def _tx(account, *, external_id, amount, tx_type, category, booked_at):
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description=category,
        amount=Decimal(amount),
        type=tx_type,
        category=category,
        booked_at=timezone.make_aware(timezone.datetime(*booked_at)),
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --------------------------------------------------------------------------
# build_savings_rate_trend
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_savings_rate_trend_returns_months_oldest_to_newest_ending_at_target(user, account):
    _tx(
        account,
        external_id="tx-jun",
        amount="1000",
        tx_type=TransactionType.CREDIT,
        category="salario",
        booked_at=(2026, 6, 10),
    )
    _tx(
        account,
        external_id="tx-jul",
        amount="2000",
        tx_type=TransactionType.CREDIT,
        category="salario",
        booked_at=(2026, 7, 10),
    )
    _tx(
        account,
        external_id="tx-aug",
        amount="3000",
        tx_type=TransactionType.CREDIT,
        category="salario",
        booked_at=(2026, 8, 10),
    )

    trend = build_savings_rate_trend(user, year=2026, month=8, months=3)

    assert [(item["year"], item["month"]) for item in trend] == [(2026, 6), (2026, 7), (2026, 8)]
    assert [item["income"] for item in trend] == [Decimal("1000"), Decimal("2000"), Decimal("3000")]


@pytest.mark.django_db
def test_savings_rate_trend_default_is_six_months(user):
    trend = build_savings_rate_trend(user, year=2026, month=8)

    assert len(trend) == 6
    assert (trend[-1]["year"], trend[-1]["month"]) == (2026, 8)
    assert (trend[0]["year"], trend[0]["month"]) == (2026, 3)


# --------------------------------------------------------------------------
# build_category_deltas_for_month
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_category_deltas_compare_against_the_previous_month(user, account):
    _tx(
        account,
        external_id="tx-jul-food",
        amount="300",
        tx_type=TransactionType.DEBIT,
        category="alimentacao",
        booked_at=(2026, 7, 5),
    )
    _tx(
        account,
        external_id="tx-aug-food",
        amount="500",
        tx_type=TransactionType.DEBIT,
        category="alimentacao",
        booked_at=(2026, 8, 5),
    )
    _tx(
        account,
        external_id="tx-aug-transport",
        amount="100",
        tx_type=TransactionType.DEBIT,
        category="transporte",
        booked_at=(2026, 8, 6),
    )

    deltas = build_category_deltas_for_month(user, year=2026, month=8)

    by_category = {item["category"]: item for item in deltas}
    assert by_category["alimentacao"]["current_amount"] == Decimal("500")
    assert by_category["alimentacao"]["previous_amount"] == Decimal("300")
    assert by_category["alimentacao"]["delta"] == Decimal("200")
    assert by_category["transporte"]["previous_amount"] == Decimal("0")
    assert by_category["transporte"]["delta"] == Decimal("100")
    # Maior aumento primeiro.
    assert deltas[0]["category"] == "alimentacao"


@pytest.mark.django_db
def test_category_deltas_exclude_internal_transfers(user, account):
    tx = _tx(
        account,
        external_id="tx-cc",
        amount="1000",
        tx_type=TransactionType.DEBIT,
        category="fatura",
        booked_at=(2026, 8, 5),
    )
    tx.provider_category = "Credit Card Payment"
    tx.save(update_fields=["provider_category"])

    deltas = build_category_deltas_for_month(user, year=2026, month=8)

    assert deltas == []


# --------------------------------------------------------------------------
# build_monthly_review_summary
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_monthly_review_summary_creates_the_review_row(user):
    assert not MonthlyReview.objects.filter(user=user, year=2026, month=8).exists()

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert summary["review"].year == 2026
    assert summary["review"].month == 8
    assert MonthlyReview.objects.filter(user=user, year=2026, month=8).exists()


@pytest.mark.django_db
def test_monthly_review_summary_is_idempotent(user):
    first = build_monthly_review_summary(user, year=2026, month=8)
    second = build_monthly_review_summary(user, year=2026, month=8)

    assert first["review"].id == second["review"].id
    assert MonthlyReview.objects.filter(user=user, year=2026, month=8).count() == 1


@pytest.mark.django_db
def test_net_worth_delta_is_none_with_fewer_than_two_snapshots(user):
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 8, 15), net_worth=Decimal("1000"))

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert summary["net_worth_delta"] is None
    assert summary["current_net_worth"] == Decimal("1000")


@pytest.mark.django_db
def test_net_worth_delta_compares_against_the_previous_period(user):
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 7, 31), net_worth=Decimal("1000"))
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 8, 20), net_worth=Decimal("1500"))

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert summary["net_worth_delta"] == Decimal("500")


@pytest.mark.django_db
def test_achievement_when_savings_rate_beats_the_three_month_average(user, account):
    for month in (5, 6, 7):
        _tx(
            account,
            external_id=f"tx-income-{month}",
            amount="1000",
            tx_type=TransactionType.CREDIT,
            category="salario",
            booked_at=(2026, month, 5),
        )
        _tx(
            account,
            external_id=f"tx-expense-{month}",
            amount="900",
            tx_type=TransactionType.DEBIT,
            category="contas",
            booked_at=(2026, month, 10),
        )
    # Agosto: taxa de poupanca de 80%, bem acima da media de mai-jun-jul (~10%).
    _tx(
        account,
        external_id="tx-income-8",
        amount="1000",
        tx_type=TransactionType.CREDIT,
        category="salario",
        booked_at=(2026, 8, 5),
    )
    _tx(
        account,
        external_id="tx-expense-8",
        amount="200",
        tx_type=TransactionType.DEBIT,
        category="contas",
        booked_at=(2026, 8, 10),
    )

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert any("acima da média" in item for item in summary["achievements"])


@pytest.mark.django_db
def test_no_achievement_when_savings_rate_is_below_the_average(user, account):
    for month in (5, 6, 7):
        _tx(
            account,
            external_id=f"tx-income-{month}",
            amount="1000",
            tx_type=TransactionType.CREDIT,
            category="salario",
            booked_at=(2026, month, 5),
        )
        _tx(
            account,
            external_id=f"tx-expense-{month}",
            amount="100",
            tx_type=TransactionType.DEBIT,
            category="contas",
            booked_at=(2026, month, 10),
        )
    # Agosto: taxa de poupanca de 10%, abaixo da media de mai-jun-jul (90%).
    _tx(
        account,
        external_id="tx-income-8",
        amount="1000",
        tx_type=TransactionType.CREDIT,
        category="salario",
        booked_at=(2026, 8, 5),
    )
    _tx(
        account,
        external_id="tx-expense-8",
        amount="900",
        tx_type=TransactionType.DEBIT,
        category="contas",
        booked_at=(2026, 8, 10),
    )

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert not any("acima da média" in item for item in summary["achievements"])


@pytest.mark.django_db
def test_achievement_lists_goals_completed_within_the_month(user):
    goal = FinancialGoal.objects.create(
        user=user,
        name="Viagem",
        target_amount=Decimal("1000"),
        current_amount=Decimal("1000"),
        status=GoalStatus.ACHIEVED,
    )
    # `updated_at` tem `auto_now=True`: `.save()` sempre sobrescreveria com o
    # instante real. `.update()` no queryset contorna isso para simular uma
    # meta concluida numa data de teste controlada.
    FinancialGoal.objects.filter(pk=goal.pk).update(
        updated_at=timezone.make_aware(timezone.datetime(2026, 8, 15))
    )

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert any("Viagem" in item for item in summary["achievements"])


@pytest.mark.django_db
def test_goal_completed_in_a_different_month_is_not_listed(user):
    goal = FinancialGoal.objects.create(
        user=user,
        name="Viagem",
        target_amount=Decimal("1000"),
        current_amount=Decimal("1000"),
        status=GoalStatus.ACHIEVED,
    )
    FinancialGoal.objects.filter(pk=goal.pk).update(
        updated_at=timezone.make_aware(timezone.datetime(2026, 7, 15))
    )

    summary = build_monthly_review_summary(user, year=2026, month=8)

    assert summary["achievements"] == []


# --------------------------------------------------------------------------
# REST: GET/PATCH /api/v1/monthly-review/
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_creates_and_returns_the_review(user):
    response = _client(user).get(URL, {"year": 2026, "month": 8})

    assert response.status_code == 200
    assert response.data["review"]["year"] == 2026
    assert response.data["review"]["month"] == 8
    assert response.data["review"]["adjustments"] == []
    assert response.data["review"]["completed_at"] is None
    assert MonthlyReview.objects.filter(user=user, year=2026, month=8).exists()


@pytest.mark.django_db
def test_get_defaults_to_the_current_month(user):
    today = timezone.localdate()

    response = _client(user).get(URL)

    assert response.status_code == 200
    assert response.data["review"]["year"] == today.year
    assert response.data["review"]["month"] == today.month


@pytest.mark.django_db
def test_patch_saves_adjustments(user):
    response = _client(user).patch(
        f"{URL}?year=2026&month=8",
        {"adjustments": ["Cortar assinatura", "Aumentar aporte"]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["adjustments"] == ["Cortar assinatura", "Aumentar aporte"]
    review = MonthlyReview.objects.get(user=user, year=2026, month=8)
    assert review.adjustments == ["Cortar assinatura", "Aumentar aporte"]


@pytest.mark.django_db
def test_patch_rejects_more_than_three_adjustments(user):
    response = _client(user).patch(
        f"{URL}?year=2026&month=8",
        {"adjustments": ["a", "b", "c", "d"]},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_patch_marks_and_unmarks_completed(user):
    client = _client(user)

    marked = client.patch(f"{URL}?year=2026&month=8", {"completed": True}, format="json")
    assert marked.data["completed_at"] is not None

    unmarked = client.patch(f"{URL}?year=2026&month=8", {"completed": False}, format="json")
    assert unmarked.data["completed_at"] is None


@pytest.mark.django_db
def test_review_is_scoped_to_the_user(user, other_user):
    MonthlyReview.objects.create(user=other_user, year=2026, month=8, adjustments=["do outro"])

    response = _client(user).get(URL, {"year": 2026, "month": 8})

    assert response.data["review"]["adjustments"] == []


@pytest.mark.django_db
def test_get_requires_authentication():
    response = APIClient().get(URL, {"year": 2026, "month": 8})

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_patch_requires_authentication():
    response = APIClient().patch(f"{URL}?year=2026&month=8", {"completed": True}, format="json")

    assert response.status_code in (401, 403)
