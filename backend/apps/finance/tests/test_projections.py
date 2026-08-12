"""Testes do simulador de futuro financeiro (`projections.py`).

Cobre a matematica pura (valor futuro com aporte, cenario de estresse, pontos de
alavancagem) com valores calculados a mao, o resolver GraphQL que expoe tudo isso,
e a garantia de que extrair `DEFAULT_SCENARIO_RATES` para
`resolve_financial_freedom_projection` nao mudou o comportamento daquele resolver
(regressao da refatoracao desta mudanca).
"""

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.finance.models import FinancialGoal, GoalStatus, Transaction, TransactionType
from apps.finance.projections import (
    DEFAULT_SCENARIO_RATES,
    build_future_projection,
    build_leverage_points,
    project_net_worth_at_horizon,
    project_stress_scenario,
    serialize_future_projection,
)
from config.schema import schema


def execute(query, user=None):
    request = RequestFactory().post("/graphql/")
    request.user = user
    result = schema.execute(query, context_value=request)
    assert not result.errors, result.errors
    return result.data


# --------------------------------------------------------------------------
# project_net_worth_at_horizon
# --------------------------------------------------------------------------


def test_zero_months_returns_current_net_worth():
    result = project_net_worth_at_horizon(Decimal("1000"), Decimal("100"), Decimal("0.08"), 0)

    assert result == Decimal("1000")


def test_zero_rate_is_simple_accumulation():
    # Sem juros, 12 meses de aporte de 100 somam 1200 ao principal.
    result = project_net_worth_at_horizon(Decimal("1000"), Decimal("100"), Decimal("0"), 12)

    assert result == Decimal("2200")


def test_known_future_value_with_monthly_compounding():
    # PV=0, PMT=100, 12% a.a. (1% a.m.), n=12: FV = 100 * ((1.01^12 - 1) / 0.01).
    result = project_net_worth_at_horizon(Decimal("0"), Decimal("100"), Decimal("0.12"), 12)

    expected = Decimal("100") * ((Decimal("1.01") ** 12 - 1) / Decimal("0.01"))
    assert abs(result - expected) < Decimal("0.01")


def test_negative_contribution_models_a_withdrawal():
    # Hiato de renda: aporte negativo reduz o principal em vez de crescer.
    result = project_net_worth_at_horizon(Decimal("10000"), Decimal("-500"), Decimal("0"), 3)

    assert result == Decimal("8500")


# --------------------------------------------------------------------------
# project_stress_scenario
# --------------------------------------------------------------------------


def test_stress_scenario_applies_shock_and_gap_before_recovering():
    result = project_stress_scenario(
        Decimal("10000"),
        Decimal("500"),
        Decimal("0"),
        6,
        shock_pct=Decimal("0.20"),
        income_gap_months=2,
    )

    # Choque: 10000 * 0.8 = 8000. 2 meses sem aporte, taxa 0 -> continua 8000.
    # 4 meses restantes com aporte de 500, taxa 0 -> +2000.
    assert result == Decimal("10000.00")


def test_stress_scenario_gap_longer_than_horizon_is_capped():
    result = project_stress_scenario(
        Decimal("1000"),
        Decimal("500"),
        Decimal("0"),
        1,
        shock_pct=Decimal("0.10"),
        income_gap_months=5,
    )

    # So 1 mes disponivel: o hiato nao pode consumir mais do que o horizonte tem.
    assert result == Decimal("900")


def test_stress_scenario_with_zero_months_returns_current_net_worth():
    result = project_stress_scenario(Decimal("1000"), Decimal("500"), Decimal("0.08"), 0)

    assert result == Decimal("1000")


# --------------------------------------------------------------------------
# build_leverage_points
# --------------------------------------------------------------------------


def test_leverage_points_are_sorted_by_impact_descending():
    points = build_leverage_points(
        current_net_worth=Decimal("50000"),
        monthly_contribution=Decimal("1000"),
        monthly_income=Decimal("5000"),
        base_rate=Decimal("0.08"),
    )

    impacts = [point["impact"] for point in points]
    assert impacts == sorted(impacts, reverse=True)
    assert len(points) <= 3


def test_leverage_points_skip_savings_candidates_without_income():
    points = build_leverage_points(
        current_net_worth=Decimal("50000"),
        monthly_contribution=Decimal("1000"),
        monthly_income=Decimal("0"),
        base_rate=Decimal("0.08"),
    )

    assert all("savings" not in point["key"] for point in points)
    # Os dois candidatos de retorno assumido continuam validos sem renda.
    assert len(points) == 2


# --------------------------------------------------------------------------
# build_future_projection
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_future_projection_for_a_user_with_no_data_does_not_explode(user):
    data = build_future_projection(user)

    assert data["current_net_worth"] == Decimal("0")
    assert data["monthly_contribution"] == Decimal("0")
    for series in data["scenarios"].values():
        assert all(value == Decimal("0") for value in series.values())
    assert data["goals"] == []


@pytest.mark.django_db
def test_future_projection_covers_every_default_scenario(user):
    data = build_future_projection(user)

    assert set(data["scenarios"].keys()) == set(DEFAULT_SCENARIO_RATES.keys())
    assert data["horizons"] == [5, 10, 20]


@pytest.mark.django_db
def test_goal_with_future_target_date_and_covered_shortfall_is_on_track(user, account):
    for month in (5, 6, 7):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-income-{month}",
            description="Salario",
            amount=Decimal("5000.00"),
            type=TransactionType.CREDIT,
            booked_at=timezone.make_aware(timezone.datetime(2026, month, 10)),
        )
    goal = FinancialGoal.objects.create(
        user=user,
        name="Reserva",
        target_amount=Decimal("100.00"),
        current_amount=Decimal("90.00"),
        target_date=date.today() + timedelta(days=365),
        status=GoalStatus.ACTIVE,
    )

    data = build_future_projection(user)

    [result] = [g for g in data["goals"] if g["id"] == goal.id]
    assert result["remaining_needed"] == Decimal("10.00")
    assert result["on_track"] is True
    assert result["shortfall"] == Decimal("0")


@pytest.mark.django_db
def test_goal_with_target_date_in_the_past_has_zero_projected_growth(user):
    goal = FinancialGoal.objects.create(
        user=user,
        name="Meta vencida",
        target_amount=Decimal("1000.00"),
        current_amount=Decimal("0"),
        target_date=date.today() - timedelta(days=10),
        status=GoalStatus.ACTIVE,
    )

    data = build_future_projection(user)

    [result] = [g for g in data["goals"] if g["id"] == goal.id]
    assert result["projected_growth"] == Decimal("0")
    assert result["on_track"] is False


@pytest.mark.django_db
def test_paused_and_dateless_goals_are_excluded_from_viability(user):
    FinancialGoal.objects.create(
        user=user,
        name="Pausada",
        target_amount=Decimal("1000"),
        target_date=date.today() + timedelta(days=30),
        status=GoalStatus.PAUSED,
    )
    FinancialGoal.objects.create(
        user=user,
        name="Sem data",
        target_amount=Decimal("1000"),
        status=GoalStatus.ACTIVE,
    )

    data = build_future_projection(user)

    assert data["goals"] == []


# --------------------------------------------------------------------------
# serialize_future_projection
# --------------------------------------------------------------------------


def test_serialize_converts_decimal_and_date_to_json_safe_values():
    raw = {
        "current_net_worth": Decimal("1000.50"),
        "monthly_contribution": Decimal("200"),
        "horizons": [5, 10],
        "scenarios": {"base": {5: Decimal("2000"), 10: Decimal("4000")}},
        "stress": {5: Decimal("1500"), 10: Decimal("3000")},
        "leverage_points": [
            {
                "key": "k",
                "label": "l",
                "projected_net_worth": Decimal("100"),
                "impact": Decimal("10"),
            }
        ],
        "goals": [
            {
                "id": 1,
                "name": "Meta",
                "target_amount": Decimal("500"),
                "target_date": date(2030, 1, 1),
                "on_track": True,
                "shortfall": Decimal("0"),
                "projected_growth": Decimal("50"),
                "remaining_needed": Decimal("0"),
            }
        ],
    }

    serialized = serialize_future_projection(raw)

    assert serialized["current_net_worth"] == 1000.5
    assert serialized["scenarios"]["base"] == {"5": 2000.0, "10": 4000.0}
    assert serialized["goals"][0]["target_date"] == "2030-01-01"
    assert isinstance(serialized["goals"][0]["target_amount"], float)


# --------------------------------------------------------------------------
# Resolver GraphQL
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_future_projection_resolves_over_graphql(user, account):
    data = execute(
        """{
          futureProjection {
            currentNetWorth
            horizons
            scenarios { name values { years netWorth } }
            stress { years netWorth }
            leveragePoints { key label impact }
            goals { name onTrack }
          }
        }""",
        user=user,
    )

    projection = data["futureProjection"]
    assert projection is not None
    assert projection["horizons"] == [5, 10, 20]
    assert {s["name"] for s in projection["scenarios"]} == {
        "conservative",
        "base",
        "aggressive",
    }


@pytest.mark.django_db
def test_future_projection_returns_null_for_anonymous():
    from django.contrib.auth.models import AnonymousUser

    data = execute("{ futureProjection { currentNetWorth } }", user=AnonymousUser())

    assert data["futureProjection"] is None


# --------------------------------------------------------------------------
# Regressao: `resolve_financial_freedom_projection` apos extrair
# DEFAULT_SCENARIO_RATES do dict local hardcoded.
# --------------------------------------------------------------------------


def test_default_scenario_rates_are_4_8_12_percent():
    """Trava os numeros em si -- os testes abaixo usam esta mesma constante para
    recalcular o esperado, entao nao pegariam um valor errado aqui sozinhos."""
    assert DEFAULT_SCENARIO_RATES == {
        "conservative": Decimal("0.04"),
        "base": Decimal("0.08"),
        "aggressive": Decimal("0.12"),
    }


def _expected_months_to_target(target_net_worth, net_worth, avg_savings, annual_rate):
    """Mesma formula de anuidade que o resolver usa, escrita de forma
    independente: se o resolver passar a reusar a mesma taxa nos tres cenarios
    (ou perder a referencia a `DEFAULT_SCENARIO_RATES`), o valor aqui diverge."""
    if avg_savings <= 0 or net_worth >= target_net_worth:
        return 0
    monthly_rate = annual_rate / 12
    denom = avg_savings + net_worth * monthly_rate
    if denom <= 0:
        return 999
    numerator = target_net_worth * monthly_rate + avg_savings
    months = int(math.log(numerator / denom) / math.log(1 + monthly_rate))
    return max(0, months)


@pytest.mark.django_db
def test_extracting_default_scenario_rates_did_not_change_financial_freedom_projection(
    user, account
):
    for month in (5, 6, 7):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-income-{month}",
            description="Salario",
            amount=Decimal("5000.00"),
            type=TransactionType.CREDIT,
            booked_at=timezone.make_aware(timezone.datetime(2026, month, 10)),
        )
        Transaction.objects.create(
            account=account,
            external_id=f"tx-expense-{month}",
            description="Contas",
            amount=Decimal("3000.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.make_aware(timezone.datetime(2026, month, 15)),
        )

    data = execute(
        """{
          financialFreedomProjection {
            currentNetWorth
            monthlySavings
            targetNetWorth
            conservativeMonths
            baseMonths
            aggressiveMonths
          }
        }""",
        user=user,
    )
    projection = data["financialFreedomProjection"]

    for name, field in (
        ("conservative", "conservativeMonths"),
        ("base", "baseMonths"),
        ("aggressive", "aggressiveMonths"),
    ):
        expected = _expected_months_to_target(
            projection["targetNetWorth"],
            projection["currentNetWorth"],
            projection["monthlySavings"],
            float(DEFAULT_SCENARIO_RATES[name]),
        )
        assert projection[field] == expected, name

    # Taxa maior encurta o tempo pro mesmo alvo -- se as tres virassem a mesma
    # taxa por engano, os tres meses empatariam.
    assert (
        projection["conservativeMonths"]
        > projection["baseMonths"]
        > projection["aggressiveMonths"]
        > 0
    )
