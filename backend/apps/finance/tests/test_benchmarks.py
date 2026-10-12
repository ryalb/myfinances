"""Testes do CDI/IPCA acumulado usado como regua da tela de investimentos."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.finance.benchmarks import build_market_benchmarks, cdi_accumulated, ipca_accumulated
from apps.finance.models import MarketIndexKind, MarketIndexRate

MARKET_BENCHMARKS_URL = "/api/v1/market-benchmarks/"

TODAY = date(2026, 10, 11)


def _cdi_daily(start: date, end: date, value: str = "0.05") -> None:
    day = start
    while day <= end:
        MarketIndexRate.objects.create(
            kind=MarketIndexKind.CDI, reference_date=day, value=Decimal(value)
        )
        day += timedelta(days=1)


def _ipca_months(values: list[str]) -> None:
    # Mais recente primeiro: setembro, agosto, julho...
    year, month = 2026, 9
    for value in values:
        MarketIndexRate.objects.create(
            kind=MarketIndexKind.IPCA, reference_date=date(year, month, 1), value=Decimal(value)
        )
        month -= 1
        if month == 0:
            year, month = year - 1, 12


@pytest.mark.django_db
def test_cdi_accumulated_compounds_daily_rates_inside_the_window():
    _cdi_daily(date(2026, 10, 1), date(2026, 10, 3), "1")

    result = cdi_accumulated(date(2026, 9, 30), date(2026, 10, 3))

    # 1,01^3 - 1 = 3,0301%
    assert result == pytest.approx(Decimal("3.0301"))


@pytest.mark.django_db
def test_cdi_accumulated_is_none_when_history_does_not_reach_the_window_start():
    _cdi_daily(TODAY - timedelta(days=60), TODAY)

    assert cdi_accumulated(TODAY - timedelta(days=30), TODAY) is not None
    assert cdi_accumulated(TODAY - timedelta(days=365), TODAY) is None


@pytest.mark.django_db
def test_ipca_accumulated_uses_last_published_months():
    _ipca_months(["1", "1", "1", "5"])

    # So os 3 mais recentes entram: 1,01^3 - 1
    assert ipca_accumulated(3) == pytest.approx(Decimal("3.0301"))


@pytest.mark.django_db
def test_ipca_accumulated_is_none_without_enough_months():
    _ipca_months(["0.5", "0.4"])

    assert ipca_accumulated(3) is None


@pytest.mark.django_db
def test_build_market_benchmarks_reports_annual_rate_and_windows():
    _cdi_daily(TODAY - timedelta(days=100), TODAY, "0.05")
    _ipca_months(["0.4"] * 12)

    benchmarks = build_market_benchmarks(today=TODAY)

    assert benchmarks["cdi"]["as_of"] == TODAY
    # 1,0005^252 - 1 ~ 13,4%
    assert benchmarks["cdi"]["annual_rate"] == pytest.approx(Decimal("13.42"), abs=Decimal("0.01"))
    assert benchmarks["cdi"]["m1"] is not None
    assert benchmarks["cdi"]["m3"] > benchmarks["cdi"]["m1"]
    assert benchmarks["cdi"]["m12"] is None
    assert benchmarks["ipca"]["m12"] is not None


@pytest.mark.django_db
def test_market_benchmarks_endpoint_requires_auth():
    response = APIClient().get(MARKET_BENCHMARKS_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_market_benchmarks_endpoint_returns_nulls_without_data(user):
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(MARKET_BENCHMARKS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "cdi": {"as_of": None, "annual_rate": None, "m1": None, "m3": None, "m12": None},
        "ipca": {"as_of": None, "m1": None, "m3": None, "m12": None},
        "cdi_since": [],
    }


@pytest.mark.django_db
def test_build_market_benchmarks_reports_cdi_since_each_purchase_date():
    _cdi_daily(date(2026, 10, 1), TODAY, "1")

    benchmarks = build_market_benchmarks(
        today=TODAY, since_dates=[date(2026, 10, 9), date(2026, 10, 9), date(2020, 1, 1), TODAY]
    )

    # Duplicada sai uma vez; data sem historico sai None; hoje (janela vazia) sai fora.
    assert benchmarks["cdi_since"] == [
        {"date": date(2020, 1, 1), "value": None},
        {"date": date(2026, 10, 9), "value": pytest.approx(Decimal("2.01"))},
    ]


@pytest.mark.django_db
def test_market_benchmarks_endpoint_rejects_malformed_since(user):
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(MARKET_BENCHMARKS_URL, {"since": "2026-01-08,ontem"})

    assert response.status_code == 400
