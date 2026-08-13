"""Otimizador automatico de financas (guidance-only): classificacao de gasto,
realizado por bucket e o alvo x atual comparado como % da renda do mes.

Zero integracao de pagamentos: o app so le dados via Pluggy, entao a saida
deste modulo e sempre numero + orientacao, nunca uma transferencia real.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.budget_buckets import (
    build_bucket_actuals_for_month,
    build_bucket_drift,
    classify_transaction_bucket,
)
from apps.finance.models import (
    Account,
    AccountType,
    BudgetBucket,
    BudgetBucketTarget,
    FinanceTag,
    FinanceTagKind,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
    Transaction,
    TransactionType,
)

TARGETS_URL = "/api/v1/budget-bucket-targets/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _tx(account, *, external_id, amount, tx_type, category="", booked_at):
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description="mov",
        amount=Decimal(amount),
        type=tx_type,
        category=category,
        booked_at=timezone.make_aware(timezone.datetime(*booked_at)),
    )


# --------------------------------------------------------------------------
# classify_transaction_bucket
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,expected",
    [
        ("Moradia", BudgetBucket.FIXED_EXPENSES),
        ("Saúde", BudgetBucket.FIXED_EXPENSES),
        ("Educação", BudgetBucket.FIXED_EXPENSES),
        ("Lazer", BudgetBucket.DISCRETIONARY),
        ("Alimentação", BudgetBucket.DISCRETIONARY),
        ("", BudgetBucket.DISCRETIONARY),
    ],
)
def test_classify_transaction_bucket(category, expected):
    assert classify_transaction_bucket(category) == expected


# --------------------------------------------------------------------------
# build_bucket_actuals_for_month
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_actuals_classify_debit_by_category(user, account):
    _tx(
        account,
        external_id="tx-1",
        amount="500",
        tx_type=TransactionType.DEBIT,
        category="Moradia",
        booked_at=(2026, 8, 5),
    )
    _tx(
        account,
        external_id="tx-2",
        amount="200",
        tx_type=TransactionType.DEBIT,
        category="Lazer",
        booked_at=(2026, 8, 6),
    )

    totals = build_bucket_actuals_for_month(user, 2026, 8)

    assert totals[BudgetBucket.FIXED_EXPENSES] == Decimal("500")
    assert totals[BudgetBucket.DISCRETIONARY] == Decimal("200")


@pytest.mark.django_db
def test_actuals_subscription_payment_counts_once_as_fixed_expense(user, account):
    subscription = Subscription.objects.create(
        user=user,
        name="Netflix",
        category=SubscriptionCategory.STREAMING,
        amount=Decimal("50"),
        due_day=10,
    )
    tx = _tx(
        account,
        external_id="tx-netflix",
        amount="50",
        tx_type=TransactionType.DEBIT,
        category="Lazer",
        booked_at=(2026, 8, 10),
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date=date(2026, 8, 10),
        status=SubscriptionStatus.PAID,
        paid_amount=Decimal("50"),
        matched_transaction=tx,
    )

    totals = build_bucket_actuals_for_month(user, 2026, 8)

    # Contado uma vez via assinatura, nao de novo via categoria "Lazer".
    assert totals[BudgetBucket.FIXED_EXPENSES] == Decimal("50")
    assert totals[BudgetBucket.DISCRETIONARY] == Decimal("0")


@pytest.mark.django_db
def test_actuals_subscription_without_matched_transaction_still_counts(user):
    subscription = Subscription.objects.create(
        user=user,
        name="Ginásio",
        category=SubscriptionCategory.OTHER,
        amount=Decimal("80"),
        due_day=5,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date=date(2026, 8, 5),
        status=SubscriptionStatus.PAID,
        paid_amount=Decimal("80"),
    )

    totals = build_bucket_actuals_for_month(user, 2026, 8)

    assert totals[BudgetBucket.FIXED_EXPENSES] == Decimal("80")


@pytest.mark.django_db
def test_actuals_pending_subscription_is_not_counted(user):
    subscription = Subscription.objects.create(
        user=user,
        name="Ginásio",
        category=SubscriptionCategory.OTHER,
        amount=Decimal("80"),
        due_day=5,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription, due_date=date(2026, 8, 5), status=SubscriptionStatus.PENDING
    )

    totals = build_bucket_actuals_for_month(user, 2026, 8)

    assert totals[BudgetBucket.FIXED_EXPENSES] == Decimal("0")


@pytest.mark.django_db
def test_actuals_credit_to_tagged_account_counts_toward_its_bucket(user, connection):
    brokerage = Account.objects.create(
        connection=connection, external_id="acc-brok", name="Corretora", type=AccountType.BROKERAGE
    )
    FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.BUDGET_BUCKET,
        value=BudgetBucket.INVESTMENTS,
        account=brokerage,
    )
    _tx(
        brokerage,
        external_id="tx-aporte",
        amount="1000",
        tx_type=TransactionType.CREDIT,
        booked_at=(2026, 8, 15),
    )

    totals = build_bucket_actuals_for_month(user, 2026, 8)

    assert totals[BudgetBucket.INVESTMENTS] == Decimal("1000")


@pytest.mark.django_db
def test_actuals_untagged_account_credit_is_ignored(user, account):
    _tx(
        account,
        external_id="tx-credit",
        amount="1000",
        tx_type=TransactionType.CREDIT,
        booked_at=(2026, 8, 15),
    )

    totals = build_bucket_actuals_for_month(user, 2026, 8)

    assert totals[BudgetBucket.INVESTMENTS] == Decimal("0")


# --------------------------------------------------------------------------
# build_bucket_drift
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_drift_percentages_are_relative_to_income(user, account):
    _tx(
        account,
        external_id="tx-income",
        amount="5000",
        tx_type=TransactionType.CREDIT,
        category="Salário",
        booked_at=(2026, 8, 1),
    )
    _tx(
        account,
        external_id="tx-moradia",
        amount="1000",
        tx_type=TransactionType.DEBIT,
        category="Moradia",
        booked_at=(2026, 8, 5),
    )
    BudgetBucketTarget.objects.create(
        user=user, bucket=BudgetBucket.FIXED_EXPENSES, target_percentage=Decimal("30")
    )

    rows = {row["bucket"]: row for row in build_bucket_drift(user, 2026, 8)}

    fixed = rows[BudgetBucket.FIXED_EXPENSES]
    assert fixed["target_percentage"] == Decimal("30")
    assert fixed["actual_percentage"] == Decimal("20")  # 1000/5000
    assert fixed["drift_pp"] == Decimal("-10")


@pytest.mark.django_db
def test_drift_all_five_buckets_always_present(user):
    rows = build_bucket_drift(user, 2026, 8)

    assert {row["bucket"] for row in rows} == set(BudgetBucket.values)


@pytest.mark.django_db
def test_drift_without_income_is_zero_percent(user):
    BudgetBucketTarget.objects.create(
        user=user, bucket=BudgetBucket.INVESTMENTS, target_percentage=Decimal("100")
    )

    rows = {row["bucket"]: row for row in build_bucket_drift(user, 2026, 8)}

    assert rows[BudgetBucket.INVESTMENTS]["actual_percentage"] == Decimal("0")


# --------------------------------------------------------------------------
# BudgetBucketTargetsAPIView
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_put_replaces_targets_in_one_batch(api):
    response = api.put(
        TARGETS_URL,
        [
            {"bucket": "fixed_expenses", "target_percentage": "55.00"},
            {"bucket": "investments", "target_percentage": "25.00"},
            {"bucket": "emergency_fund", "target_percentage": "10.00"},
            {"bucket": "goals", "target_percentage": "5.00"},
            {"bucket": "discretionary", "target_percentage": "5.00"},
        ],
        format="json",
    )

    assert response.status_code == 200
    assert len(response.data) == 5


@pytest.mark.django_db
def test_put_rejects_sum_far_from_100(api):
    response = api.put(
        TARGETS_URL, [{"bucket": "fixed_expenses", "target_percentage": "50.00"}], format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_put_rejects_duplicate_bucket(api):
    response = api.put(
        TARGETS_URL,
        [
            {"bucket": "fixed_expenses", "target_percentage": "50.00"},
            {"bucket": "fixed_expenses", "target_percentage": "50.00"},
        ],
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_get_only_returns_the_current_users_targets(api, other_user):
    BudgetBucketTarget.objects.create(
        user=other_user, bucket="fixed_expenses", target_percentage=Decimal("100")
    )

    response = api.get(TARGETS_URL)

    assert response.data == []


@pytest.mark.django_db
def test_targets_require_authentication():
    response = APIClient().get(TARGETS_URL)

    assert response.status_code in (401, 403)
