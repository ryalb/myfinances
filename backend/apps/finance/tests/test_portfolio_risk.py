"""Testes de concentracao de carteira por emissor, indexador e moeda.

Mesmo padrao de fixture de `test_allocation.py`: um `Investment` +
`InvestmentPosition` por linha, so que aqui os campos relevantes sao
issuer/indexer_additional_info/rate_type/currency, nao `kind`.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.finance.models import Investment, InvestmentPosition
from apps.finance.portfolio_risk import (
    UNKNOWN_LABEL,
    build_currency_exposure,
    build_indexer_concentration,
    build_issuer_concentration,
    serialize_concentration,
    serialize_currency_exposure,
)

PORTFOLIO_RISK_URL = "/api/v1/portfolio-risk/"


def _investment(connection, *, external_id, market_value, as_of_date="2026-08-01", **fields):
    investment = Investment.objects.create(
        connection=connection,
        external_id=external_id,
        name=external_id,
        kind="FIXED_INCOME",
        **fields,
    )
    InvestmentPosition.objects.create(
        investment=investment,
        as_of_date=as_of_date,
        quantity=1,
        unit_price=market_value,
        market_value=market_value,
    )
    return investment


def _rows_by_key(rows):
    return {row["key"]: row for row in rows}


# --------------------------------------------------------------------------
# build_issuer_concentration
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_issuer_concentration_groups_by_issuer(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("1000"), issuer="Banco A")
    _investment(connection, external_id="i2", market_value=Decimal("1000"), issuer="Banco A")
    _investment(connection, external_id="i3", market_value=Decimal("2000"), issuer="Banco B")

    rows = _rows_by_key(build_issuer_concentration(user))

    assert rows["Banco A"]["amount"] == Decimal("2000")
    assert rows["Banco A"]["percentage"] == Decimal("50")
    assert rows["Banco B"]["amount"] == Decimal("2000")
    assert rows["Banco B"]["percentage"] == Decimal("50")


@pytest.mark.django_db
def test_issuer_concentration_buckets_blank_issuer_as_unknown(user, connection):
    """Acoes/FIIs/ETF: a Pluggy nao manda `issuer` para eles -- devem contar
    como "Não informado" em vez de desaparecer do total."""
    _investment(connection, external_id="i1", market_value=Decimal("1000"), issuer="Banco A")
    _investment(connection, external_id="i2", market_value=Decimal("1000"), issuer="")

    rows = _rows_by_key(build_issuer_concentration(user))

    assert rows[UNKNOWN_LABEL]["amount"] == Decimal("1000")
    assert rows[UNKNOWN_LABEL]["percentage"] == Decimal("50")


@pytest.mark.django_db
def test_issuer_concentration_sorted_by_amount_descending(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("100"), issuer="Pequeno")
    _investment(connection, external_id="i2", market_value=Decimal("900"), issuer="Grande")

    rows = build_issuer_concentration(user)

    assert [row["key"] for row in rows] == ["Grande", "Pequeno"]


@pytest.mark.django_db
def test_issuer_concentration_ignores_other_users_investments(user, connection, other_user):
    from apps.finance.models import Connection, ConnectionStatus, FinancialInstitution

    other_institution = FinancialInstitution.objects.create(name="Outro Banco", provider_id="201")
    other_connection = Connection.objects.create(
        user=other_user,
        institution=other_institution,
        external_id="item-2",
        status=ConnectionStatus.PENDING,
    )
    _investment(connection, external_id="mine", market_value=Decimal("1000"), issuer="Meu Banco")
    _investment(
        other_connection, external_id="theirs", market_value=Decimal("5000"), issuer="Banco Deles"
    )

    rows = _rows_by_key(build_issuer_concentration(user))

    assert set(rows) == {"Meu Banco"}


# --------------------------------------------------------------------------
# build_indexer_concentration
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_indexer_concentration_groups_by_indexer_additional_info(user, connection):
    _investment(
        connection,
        external_id="i1",
        market_value=Decimal("3000"),
        indexer_additional_info="CDI",
        rate_type="POS",
    )
    _investment(
        connection,
        external_id="i2",
        market_value=Decimal("1000"),
        indexer_additional_info="IPCA",
        rate_type="POS",
    )

    rows = _rows_by_key(build_indexer_concentration(user))

    assert rows["CDI"]["amount"] == Decimal("3000")
    assert rows["CDI"]["percentage"] == Decimal("75")
    assert rows["IPCA"]["amount"] == Decimal("1000")


@pytest.mark.django_db
def test_indexer_concentration_falls_back_to_rate_type_when_indexer_missing(user, connection):
    _investment(
        connection,
        external_id="i1",
        market_value=Decimal("1000"),
        indexer_additional_info="",
        rate_type="PRE",
    )

    rows = _rows_by_key(build_indexer_concentration(user))

    assert rows["PRE"]["amount"] == Decimal("1000")


@pytest.mark.django_db
def test_indexer_concentration_buckets_missing_both_fields_as_unknown(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("1000"))

    rows = _rows_by_key(build_indexer_concentration(user))

    assert rows[UNKNOWN_LABEL]["amount"] == Decimal("1000")


# --------------------------------------------------------------------------
# build_currency_exposure
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_currency_exposure_defaults_to_all_brl(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("1000"))

    exposure = build_currency_exposure(user)

    assert exposure["brl_amount"] == Decimal("1000")
    assert exposure["brl_percentage"] == Decimal("100")
    assert exposure["foreign_amount"] == Decimal("0")
    assert exposure["foreign_percentage"] == Decimal("0")


@pytest.mark.django_db
def test_currency_exposure_splits_brl_and_foreign(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("8000"), currency="BRL")
    _investment(connection, external_id="i2", market_value=Decimal("2000"), currency="USD")

    exposure = build_currency_exposure(user)

    assert exposure["brl_percentage"] == Decimal("80")
    assert exposure["foreign_amount"] == Decimal("2000")
    assert exposure["foreign_percentage"] == Decimal("20")
    assert _rows_by_key(exposure["by_currency"])["USD"]["amount"] == Decimal("2000")


@pytest.mark.django_db
def test_currency_exposure_with_no_investments_is_all_zero(user, connection):
    exposure = build_currency_exposure(user)

    assert exposure["brl_amount"] == Decimal("0")
    assert exposure["brl_percentage"] == Decimal("0")
    assert exposure["foreign_percentage"] == Decimal("0")
    assert exposure["by_currency"] == []


# --------------------------------------------------------------------------
# serialize_*
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_serialize_concentration_converts_decimal_to_float(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("1000"), issuer="Banco A")

    serialized = serialize_concentration(build_issuer_concentration(user))

    assert serialized == [
        {"key": "Banco A", "label": "Banco A", "amount": 1000.0, "percentage": 100.0}
    ]


@pytest.mark.django_db
def test_serialize_currency_exposure_converts_decimal_to_float(user, connection):
    _investment(connection, external_id="i1", market_value=Decimal("1000"))

    serialized = serialize_currency_exposure(build_currency_exposure(user))

    assert serialized["brl_amount"] == 1000.0
    assert serialized["brl_percentage"] == 100.0
    assert serialized["by_currency"] == [
        {"key": "BRL", "label": "BRL", "amount": 1000.0, "percentage": 100.0}
    ]


# --------------------------------------------------------------------------
# PortfolioRiskAPIView
# --------------------------------------------------------------------------


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_portfolio_risk_endpoint_requires_authentication():
    response = APIClient().get(PORTFOLIO_RISK_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_portfolio_risk_endpoint_shape_with_no_investments(api):
    response = api.get(PORTFOLIO_RISK_URL)

    assert response.status_code == 200
    assert response.data == {
        "issuer_concentration": [],
        "indexer_concentration": [],
        "currency_exposure": {
            "brl_amount": "0.00",
            "brl_percentage": "0.00",
            "foreign_amount": "0.00",
            "foreign_percentage": "0.00",
            "by_currency": [],
        },
    }


@pytest.mark.django_db
def test_portfolio_risk_endpoint_reflects_investments(api, connection):
    _investment(
        connection,
        external_id="i1",
        market_value=Decimal("7000"),
        issuer="Banco A",
        indexer_additional_info="CDI",
        currency="BRL",
    )
    _investment(
        connection,
        external_id="i2",
        market_value=Decimal("3000"),
        issuer="Banco B",
        indexer_additional_info="IPCA",
        currency="USD",
    )

    response = api.get(PORTFOLIO_RISK_URL)

    assert response.status_code == 200
    issuers = {row["key"] for row in response.data["issuer_concentration"]}
    assert issuers == {"Banco A", "Banco B"}
    assert response.data["currency_exposure"]["brl_percentage"] == "70.00"
    assert response.data["currency_exposure"]["foreign_percentage"] == "30.00"


@pytest.mark.django_db
def test_portfolio_risk_endpoint_scoped_to_the_authenticated_user(api, connection, other_user):
    from apps.finance.models import Connection, ConnectionStatus, FinancialInstitution

    other_institution = FinancialInstitution.objects.create(name="Outro Banco", provider_id="202")
    other_connection = Connection.objects.create(
        user=other_user,
        institution=other_institution,
        external_id="item-3",
        status=ConnectionStatus.PENDING,
    )
    _investment(
        other_connection, external_id="theirs", market_value=Decimal("9000"), issuer="Banco Deles"
    )

    response = api.get(PORTFOLIO_RISK_URL)

    assert response.data["issuer_concentration"] == []

