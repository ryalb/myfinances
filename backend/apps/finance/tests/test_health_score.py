"""Testes do diagnostico de saude financeira (nota 0-100).

Cada componente tem faixas deterministicas (nunca um score continuo): os testes
de banda cobrem os limites de cada faixa. `build_top_actions` e testado sem
banco (funcao pura sobre dicts), o resto precisa de fixtures reais porque cada
componente le de uma tabela diferente (transacoes, cartoes, snapshots, alertas).
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import timezone

from apps.finance.health_score import (
    ACTION_TEXT,
    _alerts_score,
    _credit_utilization_score,
    _emergency_fund_score,
    _net_worth_trend_score,
    _savings_rate_score,
    build_financial_health_score,
    build_top_actions,
)
from apps.finance.models import (
    Card,
    Connection,
    ConnectionStatus,
    NetWorthSnapshot,
    Transaction,
    TransactionType,
)
from config.schema import schema

TODAY = date(2026, 8, 12)


def _tx(account, *, external_id, amount, tx_type, booked_at):
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description="mov",
        amount=Decimal(amount),
        type=tx_type,
        booked_at=timezone.make_aware(timezone.datetime(*booked_at)),
    )


def _execute(query, user=None):
    request = RequestFactory().post("/graphql/")
    request.user = user
    result = schema.execute(query, context_value=request)
    assert not result.errors, result.errors
    return result.data


# --------------------------------------------------------------------------
# _savings_rate_score
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "income,expense,expected_score",
    [
        ("1000", "750", Decimal("100")),  # 25% >= 20
        ("1000", "850", Decimal("70")),  # 15% >= 10
        ("1000", "950", Decimal("40")),  # 5% >= 0
        ("1000", "1200", Decimal("0")),  # -20% < 0
    ],
)
def test_savings_rate_score_bands(user, account, income, expense, expected_score):
    for month in (5, 6, 7):
        _tx(
            account,
            external_id=f"tx-income-{month}",
            amount=income,
            tx_type=TransactionType.CREDIT,
            booked_at=(2026, month, 5),
        )
        _tx(
            account,
            external_id=f"tx-expense-{month}",
            amount=expense,
            tx_type=TransactionType.DEBIT,
            booked_at=(2026, month, 10),
        )

    score, detail = _savings_rate_score(user, today=TODAY)

    assert score == expected_score
    assert "%" in detail


@pytest.mark.django_db
def test_savings_rate_score_without_income_history(user):
    score, _ = _savings_rate_score(user, today=TODAY)

    assert score == Decimal("40")


# --------------------------------------------------------------------------
# _emergency_fund_score
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "balance,monthly_expense,expected_score",
    [
        ("6000", "1000", Decimal("100")),  # 6 meses
        ("3000", "1000", Decimal("70")),  # 3 meses
        ("1000", "1000", Decimal("40")),  # 1 mes
        ("500", "1000", Decimal("0")),  # 0.5 mes
    ],
)
def test_emergency_fund_score_bands(user, account, balance, monthly_expense, expected_score):
    for month in (5, 6, 7):
        _tx(
            account,
            external_id=f"tx-expense-{month}",
            amount=monthly_expense,
            tx_type=TransactionType.DEBIT,
            booked_at=(2026, month, 10),
        )
    account.available_balance = Decimal(balance)
    account.save(update_fields=["available_balance"])

    score, detail = _emergency_fund_score(user, today=TODAY)

    assert score == expected_score
    assert "mês" in detail


@pytest.mark.django_db
def test_emergency_fund_score_without_expense_history_defaults_to_full_coverage(user, account):
    score, _ = _emergency_fund_score(user, today=TODAY)

    assert score == Decimal("100")


# --------------------------------------------------------------------------
# _credit_utilization_score
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "balance,limit,expected_score",
    [
        ("300", "1000", Decimal("100")),  # 30%
        ("500", "1000", Decimal("70")),  # 50%
        ("800", "1000", Decimal("40")),  # 80%
        ("900", "1000", Decimal("0")),  # 90%
    ],
)
def test_credit_utilization_score_bands(user, connection, balance, limit, expected_score):
    Card.objects.create(
        connection=connection,
        external_id="card-1",
        name="Cartão",
        last4="1234",
        credit_limit=Decimal(limit),
        current_balance=Decimal(balance),
        due_day=10,
        close_day=1,
    )

    score, detail = _credit_utilization_score(user)

    assert score == expected_score
    assert "%" in detail


@pytest.mark.django_db
def test_credit_utilization_score_without_cards(user):
    score, _ = _credit_utilization_score(user)

    assert score == Decimal("100")


# --------------------------------------------------------------------------
# _net_worth_trend_score
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_net_worth_trend_score_insufficient_history_is_neutral(user):
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 8, 10), net_worth=Decimal("1000"))

    score, detail = _net_worth_trend_score(user, today=TODAY)

    assert score == Decimal("50")
    assert "insuficiente" in detail


@pytest.mark.django_db
@pytest.mark.parametrize(
    "baseline,latest,expected_score",
    [
        (Decimal("1000"), Decimal("1100"), Decimal("100")),  # +10%
        (Decimal("1000"), Decimal("1000"), Decimal("70")),  # 0%
        (Decimal("1000"), Decimal("950"), Decimal("40")),  # -5%
        (Decimal("1000"), Decimal("700"), Decimal("0")),  # -30%
    ],
)
def test_net_worth_trend_score_bands(user, baseline, latest, expected_score):
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 5, 1), net_worth=baseline)
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 8, 10), net_worth=latest)

    score, _ = _net_worth_trend_score(user, today=TODAY)

    assert score == expected_score


@pytest.mark.django_db
def test_net_worth_trend_score_handles_zero_baseline(user):
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 5, 1), net_worth=Decimal("0"))
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 8, 10), net_worth=Decimal("500"))

    score, _ = _net_worth_trend_score(user, today=TODAY)

    assert score == Decimal("100")


# --------------------------------------------------------------------------
# _alerts_score
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_alerts_score_without_alerts_is_full(user):
    score, detail = _alerts_score(user)

    assert score == Decimal("100")
    assert "0 alerta" in detail


@pytest.mark.django_db
def test_alerts_score_penalizes_danger_alerts(user, institution):
    Connection.objects.create(
        user=user, institution=institution, external_id="broken-1", status=ConnectionStatus.ERROR
    )

    score, detail = _alerts_score(user)

    assert score == Decimal("60")  # 100 - 40 (1 alerta grave)
    assert "1 alerta" in detail


# --------------------------------------------------------------------------
# build_top_actions (funcao pura, sem banco)
# --------------------------------------------------------------------------


def _component(key, score, weight):
    return {"key": key, "label": key, "score": score, "weight": weight, "detail": ""}


def test_build_top_actions_picks_the_three_lowest_scores():
    components = [
        _component("savings_rate", Decimal("90"), Decimal("30")),
        _component("emergency_fund", Decimal("20"), Decimal("25")),
        _component("credit_utilization", Decimal("10"), Decimal("20")),
        _component("net_worth_trend", Decimal("50"), Decimal("15")),
        _component("alerts", Decimal("30"), Decimal("10")),
    ]

    actions = build_top_actions(components)

    assert actions == [
        ACTION_TEXT["credit_utilization"],
        ACTION_TEXT["emergency_fund"],
        ACTION_TEXT["alerts"],
    ]


def test_build_top_actions_breaks_ties_by_original_order():
    components = [
        _component("savings_rate", Decimal("50"), Decimal("30")),
        _component("emergency_fund", Decimal("50"), Decimal("25")),
        _component("credit_utilization", Decimal("50"), Decimal("20")),
        _component("net_worth_trend", Decimal("90"), Decimal("15")),
        _component("alerts", Decimal("90"), Decimal("10")),
    ]

    actions = build_top_actions(components)

    assert actions == [
        ACTION_TEXT["savings_rate"],
        ACTION_TEXT["emergency_fund"],
        ACTION_TEXT["credit_utilization"],
    ]


def test_build_top_actions_is_empty_when_everything_is_perfect():
    components = [_component(key, Decimal("100"), Decimal("1")) for key in ACTION_TEXT]

    assert build_top_actions(components) == []


# --------------------------------------------------------------------------
# build_financial_health_score
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_build_financial_health_score_has_five_weighted_components(user):
    result = build_financial_health_score(user, today=TODAY)

    assert [c["key"] for c in result["components"]] == [
        "savings_rate",
        "emergency_fund",
        "credit_utilization",
        "net_worth_trend",
        "alerts",
    ]
    assert sum(c["weight"] for c in result["components"]) == Decimal("100")


@pytest.mark.django_db
def test_build_financial_health_score_no_data_user_does_not_explode(user):
    result = build_financial_health_score(user, today=TODAY)

    assert Decimal("0") <= result["score"] <= Decimal("100")
    assert isinstance(result["top_actions"], list)


@pytest.mark.django_db
def test_build_financial_health_score_all_components_perfect_yields_100(user, account):
    for month in (5, 6, 7):
        _tx(
            account,
            external_id=f"tx-income-{month}",
            amount="1000",
            tx_type=TransactionType.CREDIT,
            booked_at=(2026, month, 5),
        )
        _tx(
            account,
            external_id=f"tx-expense-{month}",
            amount="500",
            tx_type=TransactionType.DEBIT,
            booked_at=(2026, month, 10),
        )
    account.available_balance = Decimal("10000")
    account.save(update_fields=["available_balance"])
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 5, 1), net_worth=Decimal("1000"))
    NetWorthSnapshot.objects.create(user=user, date=date(2026, 8, 10), net_worth=Decimal("1100"))

    result = build_financial_health_score(user, today=TODAY)

    assert result["score"] == Decimal("100")
    assert result["top_actions"] == []


# --------------------------------------------------------------------------
# Resolver GraphQL
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_financial_health_score_resolves_over_graphql(user):
    data = _execute(
        """{
          financialHealthScore {
            score
            components { key label score weight detail }
            topActions
          }
        }""",
        user=user,
    )

    result = data["financialHealthScore"]
    assert result is not None
    assert len(result["components"]) == 5


@pytest.mark.django_db
def test_financial_health_score_returns_null_for_anonymous():
    data = _execute("{ financialHealthScore { score } }", user=AnonymousUser())

    assert data["financialHealthScore"] is None
