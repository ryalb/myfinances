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
    build_contribution_plan,
    classify_investment_asset_class,
    reclassifiable_investments,
    taggable_cash_accounts,
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
    PortfolioTarget,
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
# build_contribution_plan
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_contribution_plan_returns_empty_when_drift_is_empty(user):
    assert build_contribution_plan(user, Decimal("500")) == []


@pytest.mark.django_db
def test_contribution_plan_returns_empty_for_non_positive_amount(user, connection):
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("1000"))

    assert build_contribution_plan(user, Decimal("0")) == []
    assert build_contribution_plan(user, Decimal("-100")) == []


@pytest.mark.django_db
def test_contribution_plan_splits_first_contribution_by_target(user):
    PortfolioTarget.objects.create(
        user=user, asset_class="fixed_income", target_percentage=Decimal("60")
    )
    PortfolioTarget.objects.create(
        user=user, asset_class="equity_br", target_percentage=Decimal("40")
    )

    plan = {row["asset_class"]: row for row in build_contribution_plan(user, Decimal("1000"))}

    assert plan[AssetClass.FIXED_INCOME]["suggested_amount"] == Decimal("600.00")
    assert plan[AssetClass.EQUITY_BR]["suggested_amount"] == Decimal("400.00")
    assert sum(row["suggested_amount"] for row in plan.values()) == Decimal("1000.00")


@pytest.mark.django_db
def test_contribution_plan_prioritizes_underweight_class_when_insufficient(user, connection):
    PortfolioTarget.objects.create(
        user=user, asset_class="fixed_income", target_percentage=Decimal("50")
    )
    PortfolioTarget.objects.create(
        user=user, asset_class="equity_br", target_percentage=Decimal("30")
    )
    PortfolioTarget.objects.create(
        user=user, asset_class="equity_intl", target_percentage=Decimal("20")
    )
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("200"))
    _investment(connection, external_id="inv-2", kind="EQUITY", market_value=Decimal("800"))

    plan = {row["asset_class"]: row for row in build_contribution_plan(user, Decimal("500"))}

    # equity_br ja esta acima do proprio alvo mesmo depois do aporte -- nao
    # recebe nada, o aporte inteiro e rateado entre as duas classes carentes.
    assert plan[AssetClass.EQUITY_BR]["suggested_amount"] == Decimal("0.00")
    assert plan[AssetClass.FIXED_INCOME]["suggested_amount"] == Decimal("323.53")
    assert plan[AssetClass.EQUITY_INTL]["suggested_amount"] == Decimal("176.47")
    assert sum(row["suggested_amount"] for row in plan.values()) == Decimal("500.00")


@pytest.mark.django_db
def test_contribution_plan_spreads_leftover_by_target_after_closing_gaps(user, connection):
    # Alvo definido so para fixed_income (30%): equity_br entra no drift com
    # alvo 0% (saldo real sem alvo declarado), e nao deve receber dinheiro
    # novo mesmo com sobra, porque o usuario nunca pediu alocacao ali.
    PortfolioTarget.objects.create(
        user=user, asset_class="fixed_income", target_percentage=Decimal("30")
    )
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("300"))
    _investment(connection, external_id="inv-2", kind="EQUITY", market_value=Decimal("700"))

    plan = {row["asset_class"]: row for row in build_contribution_plan(user, Decimal("1000"))}

    assert plan[AssetClass.FIXED_INCOME]["suggested_amount"] == Decimal("1000.00")
    assert plan[AssetClass.EQUITY_BR]["suggested_amount"] == Decimal("0.00")


@pytest.mark.django_db
def test_contribution_plan_without_any_target_splits_evenly_without_dividing_by_zero(
    user, connection
):
    _investment(connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("1000"))
    _investment(connection, external_id="inv-2", kind="EQUITY", market_value=Decimal("500"))

    plan = build_contribution_plan(user, Decimal("100.01"))

    amounts = sorted(row["suggested_amount"] for row in plan)
    assert amounts == [Decimal("50.00"), Decimal("50.01")]
    assert sum(amounts) == Decimal("100.01")


# --------------------------------------------------------------------------
# reclassifiable_investments / taggable_cash_accounts
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_reclassifiable_investments_lists_every_investment_with_effective_class(user, connection):
    fixed_income = _investment(
        connection, external_id="inv-1", kind="FIXED_INCOME", market_value=Decimal("100")
    )
    ambiguous = _investment(
        connection, external_id="inv-2", kind="MUTUAL_FUND", market_value=Decimal("100")
    )
    tagged = _investment(
        connection, external_id="inv-3", kind="ETF", market_value=Decimal("100")
    )
    tag = FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.ASSET_CLASS,
        value=AssetClass.EQUITY_INTL,
        investment=tagged,
    )

    result = {row["id"]: row for row in reclassifiable_investments(user)}

    assert result[fixed_income.id]["asset_class"] == AssetClass.FIXED_INCOME
    assert result[fixed_income.id]["tag_id"] is None
    assert result[ambiguous.id]["asset_class"] == AssetClass.EQUITY_BR
    assert result[ambiguous.id]["tag_id"] is None
    assert result[tagged.id]["asset_class"] == AssetClass.EQUITY_INTL
    assert result[tagged.id]["tag_id"] == tag.id


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

    assert result == [
        {"id": checking.id, "name": checking.name, "type": checking.type, "tag_id": None}
    ]


@pytest.mark.django_db
def test_taggable_cash_accounts_reports_tag_id_when_marked_as_reserve(user, connection):
    from apps.finance.models import Account

    checking = Account.objects.create(
        connection=connection,
        external_id="acc-checking",
        name="Conta corrente",
        type=AccountType.CHECKING,
        available_balance=Decimal("100"),
    )
    tag = FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.ASSET_CLASS,
        value=AssetClass.CASH_RESERVE,
        account=checking,
    )

    result = taggable_cash_accounts(user)

    assert result == [
        {"id": checking.id, "name": checking.name, "type": checking.type, "tag_id": tag.id}
    ]


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
