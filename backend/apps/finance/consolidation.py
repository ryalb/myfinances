from datetime import date
from datetime import date as date_type
from decimal import Decimal

from django.db.models import Q, Sum

from .domain import classify_account_balance
from .models import (
    Account,
    Card,
    InvestmentPosition,
    NetWorthSnapshot,
    PensionPlan,
    Transaction,
    TransactionType,
)


def build_user_financial_summary(user) -> dict:
    accounts = Account.objects.filter(connection__user=user).select_related("connection")
    cards = Card.objects.filter(connection__user=user)
    pensions = PensionPlan.objects.filter(connection__user=user)
    investment_positions = InvestmentPosition.objects.filter(investment__connection__user=user)

    cash = Decimal("0")
    account_investments = Decimal("0")
    credit_card_liabilities = Decimal("0")

    for account in accounts:
        class_name, amount = classify_account_balance(account)
        if class_name == "cash":
            cash += amount
        elif class_name == "investments":
            account_investments += amount
        elif class_name == "credit_cards":
            # For credit accounts, the balance is typically what is owed.
            # We use absolute value to represent the liability amount.
            credit_card_liabilities += abs(amount)

    market_investments = (
        investment_positions.aggregate(total=Sum("market_value")).get("total") or Decimal("0")
    )
    pensions_total = pensions.aggregate(total=Sum("balance")).get("total") or Decimal("0")
    cards_total = cards.aggregate(total=Sum("current_balance")).get("total") or Decimal("0")

    assets = cash + account_investments + market_investments + pensions_total
    liabilities = credit_card_liabilities + cards_total
    net_worth = assets - liabilities

    # Identify "debts" as any negative balance in non-credit accounts (e.g., loans)
    # For now, we treat credit card balances as the primary debt source.
    # If there are other types of debts, they would be added here.
    
    return {
        "assets": assets,
        "liabilities": liabilities,
        "net_worth": net_worth,
        "breakdown": {
            "cash": cash,
            "investments": account_investments + market_investments,
            "pension": pensions_total,
            "debts": Decimal("0"), # Placeholder for other types of debt (e.g. loans)
            "credit_cards": credit_card_liabilities + cards_total,
        },
    }


def build_monthly_cash_flow_for_range(user, start_date, end_date) -> dict:
    """Build cash flow for an arbitrary date range (exclusive end)."""
    from decimal import Decimal

    transactions = Transaction.objects.filter(
        Q(account__connection__user=user) | Q(card__connection__user=user),
        booked_at__gte=start_date,
        booked_at__lt=end_date,
    )

    income = (
        transactions.filter(type=TransactionType.CREDIT).aggregate(total=Sum("amount")).get("total")
        or Decimal("0")
    )
    expenses = (
        transactions.filter(type=TransactionType.DEBIT).aggregate(total=Sum("amount")).get("total")
        or Decimal("0")
    )

    savings = income - expenses
    savings_rate = (savings / income * Decimal("100")) if income > 0 else Decimal("0")

    return {
        "income": income,
        "expenses": expenses,
        "savings": savings,
        "savings_rate": savings_rate,
    }


def build_monthly_cash_flow(user, year: int, month: int) -> dict:
    # Build range for the given month
    if month == 1:
        start = date_type(year - 1, 12, 1)
        end = date_type(year, 1, 1)
    else:
        start = date_type(year, month - 1, 1)
        end = date_type(year, month, 1)

    flow = build_monthly_cash_flow_for_range(user, start, end)

    return {
        "year": year,
        "month": month,
        "income": flow["income"],
        "expenses": flow["expenses"],
        "savings": flow["savings"],
        "savings_rate": flow["savings_rate"],
    }


def snapshot_net_worth(user, snapshot_date: date | None = None) -> NetWorthSnapshot:
    computed_date = snapshot_date or date.today()
    summary = build_user_financial_summary(user)
    snapshot, _ = NetWorthSnapshot.objects.update_or_create(
        user=user,
        date=computed_date,
        defaults={
            "assets": summary["assets"],
            "liabilities": summary["liabilities"],
            "net_worth": summary["net_worth"],
        },
    )
    return snapshot
