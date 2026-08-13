"""Alocacao de portfolio (Bogleheads-style): classificacao, alvo x atual, e as
views REST que dependem disso (`PortfolioTargetsAPIView`, `FinanceTagViewSet`).

`classify_investment_asset_class` e testado table-driven porque a taxonomia da
Pluggy (`kind`) e a fonte de ambiguidade central deste modulo -- `MUTUAL_FUND`/
`ETF`/`COE` precisam cair no default e a tag do usuario precisa vencer quando
existe.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.finance.allocation import (
    build_actual_allocation,
    build_allocation_drift,
    classify_investment_asset_class,
    taggable_cash_accounts,
    untagged_investments,
)
from apps.finance.models import (
    AccountType,
    AssetClass,
    FinanceTag,
    FinanceTagKind,
    FinancialGoal,
    GoalStatus,
    Investment,
    InvestmentPosition,
    PensionPlan,
)

TARGETS_URL = "/api/v1/portfolio-targets/"
TAGS_URL = "/api/v1/finance-tags/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _investment(connection, *, external_id, kind, market_value, as_of_date="2026-08-01"):
    investment = Investment.objects.create(
        connection=connection, external_id=external_id, name=external_id, kind=kind
    )
    InvestmentPosition.objects.create(
        investment=investment,
        as_of_date=as_of_date,
        quantity=1,
        unit_price=market_value,
        market_value=market_value,
    )
    return investment


# --------------------------------------------------------------------------
# classify_investment_asset_class
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("FIXED_INCOME", AssetClass.FIXED_INCOME),
        ("fixed_income", AssetClass.FIXED_INCOME),
        ("EQUITY", AssetClass.EQUITY_BR),
        ("MUTUAL_FUND", AssetClass.EQUITY_BR),
        ("ETF", AssetClass.EQUITY_BR),
        ("COE", AssetClass.EQUITY_BR),
        ("SOMETHING_UNKNOWN", AssetClass.EQUITY_BR),
    ],
)
def test_classify_by_kind_without_tag(kind, expected):
    investment = Investment(kind=kind)

    assert classify_investment_asset_class(investment, tag=None) == expected


def test_classify_tag_wins_over_kind():
    investment = Investment(kind="ETF")
    tag = FinanceTag(kind=FinanceTagKind.ASSET_CLASS, value=AssetClass.EQUITY_INTL)

    assert classify_investment_asset_class(investment, tag=tag) == AssetClass.EQUITY_INTL


# --------------------------------------------------------------------------
# build_actual_allocation
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_actual_allocation_classifies_investments_by_kind(user, connection):
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("1000"))
    _investment(connection, external_id="inv-2", kind="EQUITY", market_value=Decimal("500"))

    allocation = {row["asset_class"]: row["amount"] for row in build_actual_allocation(user)}

    assert allocation[AssetClass.FIXED_INCOME] == Decimal("1000")
    assert allocation[AssetClass.EQUITY_BR] == Decimal("500")


@pytest.mark.django_db
def test_actual_allocation_ambiguous_kind_follows_tag(user, connection):
    investment = _investment(
        connection, external_id="inv-1", kind="MUTUAL_FUND", market_value=Decimal("1000")
    )
    FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.ASSET_CLASS,
        value=AssetClass.EQUITY_INTL,
        investment=investment,
    )

    allocation = {row["asset_class"]: row["amount"] for row in build_actual_allocation(user)}

    assert allocation[AssetClass.EQUITY_INTL] == Decimal("1000")
    assert AssetClass.EQUITY_BR not in allocation


@pytest.mark.django_db
def test_actual_allocation_pension_is_always_its_own_class(user):
    PensionPlan.objects.create(
        user=user, name="PGBL", provider="Seguradora", balance=Decimal("2000")
    )

    allocation = {row["asset_class"]: row["amount"] for row in build_actual_allocation(user)}

    assert allocation[AssetClass.PENSION] == Decimal("2000")


@pytest.mark.django_db
def test_actual_allocation_ignores_untagged_account_balance(user, account):
    allocation = build_actual_allocation(user)

    assert allocation == []


@pytest.mark.django_db
def test_actual_allocation_counts_tagged_cash_account(user, account):
    FinanceTag.objects.create(
        user=user, kind=FinanceTagKind.ASSET_CLASS, value=AssetClass.CASH_RESERVE, account=account
    )

    allocation = {row["asset_class"]: row["amount"] for row in build_actual_allocation(user)}

    assert allocation[AssetClass.CASH_RESERVE] == account.available_balance


# --------------------------------------------------------------------------
# build_allocation_drift
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_allocation_drift_joins_target_and_actual(user, connection):
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("1000"))
    api_client = APIClient()
    api_client.force_authenticate(user)
    api_client.put(
        TARGETS_URL,
        [
            {"asset_class": "fixed_income", "target_percentage": "50.00"},
            {"asset_class": "equity_br", "target_percentage": "50.00"},
        ],
        format="json",
    )

    drift = {row["asset_class"]: row for row in build_allocation_drift(user)}

    fixed_income = drift[AssetClass.FIXED_INCOME]
    assert fixed_income["target_percentage"] == Decimal("50.00")
    assert fixed_income["actual_percentage"] == Decimal("100")
    assert fixed_income["drift_pp"] == Decimal("50.00")

    # Sem investimento nenhum, mas com alvo definido: aparece com atual 0%.
    equity = drift[AssetClass.EQUITY_BR]
    assert equity["actual_percentage"] == Decimal("0")
    assert equity["drift_pp"] == Decimal("-50.00")


@pytest.mark.django_db
def test_allocation_drift_includes_class_with_balance_but_no_target(user, connection):
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("1000"))

    drift = {row["asset_class"]: row for row in build_allocation_drift(user)}

    assert drift[AssetClass.FIXED_INCOME]["target_percentage"] == Decimal("0")
    assert drift[AssetClass.FIXED_INCOME]["actual_percentage"] == Decimal("100")


# --------------------------------------------------------------------------
# untagged_investments / taggable_cash_accounts
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_untagged_investments_lists_only_ambiguous_and_untagged(user, connection):
    ambiguous = _investment(
        connection, external_id="inv-1", kind="MUTUAL_FUND", market_value=Decimal("100")
    )
    _investment(connection, external_id="inv-2", kind="FIXED_INCOME", market_value=Decimal("100"))
    tagged_ambiguous = _investment(
        connection, external_id="inv-3", kind="ETF", market_value=Decimal("100")
    )
    FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.ASSET_CLASS,
        value=AssetClass.EQUITY_INTL,
        investment=tagged_ambiguous,
    )

    result = untagged_investments(user)

    assert result == [ambiguous]


@pytest.mark.django_db
def test_taggable_cash_accounts_excludes_brokerage_and_credit(user, connection):
    from apps.finance.models import Account

    checking = Account.objects.create(
        connection=connection,
        external_id="acc-checking",
        name="Conta corrente",
        type=AccountType.CHECKING,
        available_balance=Decimal("100"),
    )
    Account.objects.create(
        connection=connection,
        external_id="acc-brokerage",
        name="Corretora",
        type=AccountType.BROKERAGE,
        available_balance=Decimal("100"),
    )

    result = taggable_cash_accounts(user)

    assert result == [checking]


# --------------------------------------------------------------------------
# PortfolioTargetsAPIView
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_put_replaces_targets_in_one_batch(api):
    response = api.put(
        TARGETS_URL,
        [
            {"asset_class": "fixed_income", "target_percentage": "60.00"},
            {"asset_class": "equity_br", "target_percentage": "40.00"},
        ],
        format="json",
    )

    assert response.status_code == 200
    assert {row["asset_class"] for row in response.data} == {"fixed_income", "equity_br"}

    # Segundo PUT substitui o lote anterior, nao acumula.
    response = api.put(
        TARGETS_URL, [{"asset_class": "pension", "target_percentage": "100.00"}], format="json"
    )
    assert response.status_code == 200
    assert [row["asset_class"] for row in response.data] == ["pension"]


@pytest.mark.django_db
def test_put_rejects_sum_far_from_100(api):
    response = api.put(
        TARGETS_URL, [{"asset_class": "fixed_income", "target_percentage": "50.00"}], format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_put_rejects_duplicate_asset_class(api):
    response = api.put(
        TARGETS_URL,
        [
            {"asset_class": "fixed_income", "target_percentage": "50.00"},
            {"asset_class": "fixed_income", "target_percentage": "50.00"},
        ],
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_get_only_returns_the_current_users_targets(api, other_user):
    from apps.finance.models import PortfolioTarget

    PortfolioTarget.objects.create(
        user=other_user, asset_class="fixed_income", target_percentage=Decimal("100")
    )

    response = api.get(TARGETS_URL)

    assert response.data == []


@pytest.mark.django_db
def test_targets_require_authentication():
    response = APIClient().get(TARGETS_URL)

    assert response.status_code in (401, 403)


# --------------------------------------------------------------------------
# FinanceTagViewSet
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_tag_for_own_account(api, account):
    response = api.post(
        TAGS_URL,
        {"kind": "asset_class", "value": "cash_reserve", "account": account.id},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert FinanceTag.objects.get(id=response.data["id"]).account_id == account.id


@pytest.mark.django_db
def test_create_tag_rejects_another_users_account(api, other_user, institution):
    from apps.finance.models import Account, Connection, ConnectionStatus

    other_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro",
        status=ConnectionStatus.ACTIVE,
    )
    other_account = Account.objects.create(
        connection=other_connection,
        external_id="acc-outro",
        name="Conta do invasor",
        type=AccountType.CHECKING,
    )

    response = api.post(
        TAGS_URL,
        {"kind": "asset_class", "value": "cash_reserve", "account": other_account.id},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_tag_rejects_zero_targets(api):
    response = api.post(TAGS_URL, {"kind": "asset_class", "value": "cash_reserve"}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_tag_rejects_more_than_one_target(api, account, user):
    goal = FinancialGoal.objects.create(
        user=user,
        name="Viagem",
        target_amount=Decimal("1000"),
        status=GoalStatus.ACTIVE,
    )

    response = api.post(
        TAGS_URL,
        {"kind": "asset_class", "value": "cash_reserve", "account": account.id, "goal": goal.id},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_tags_can_be_filtered_by_kind(api, account, user):
    FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.ASSET_CLASS,
        value="cash_reserve",
        account=account,
    )

    response = api.get(f"{TAGS_URL}?kind=budget_bucket")
    assert response.data == []

    response = api.get(f"{TAGS_URL}?kind=asset_class")
    assert len(response.data) == 1
