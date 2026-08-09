import calendar
from datetime import date, timedelta
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
    Subscription,
    SubscriptionPayment,
    SubscriptionStatus,
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
            credit_card_liabilities += abs(amount)

    market_investments = investment_positions.aggregate(total=Sum("market_value")).get(
        "total"
    ) or Decimal("0")
    pensions_total = pensions.aggregate(total=Sum("balance")).get("total") or Decimal("0")
    cards_total = cards.aggregate(total=Sum("current_balance")).get("total") or Decimal("0")

    assets = cash + account_investments + market_investments + pensions_total
    liabilities = credit_card_liabilities + cards_total
    net_worth = assets - liabilities

    return {
        "assets": assets,
        "liabilities": liabilities,
        "net_worth": net_worth,
        "breakdown": {
            "cash": cash,
            "investments": account_investments + market_investments,
            "pension": pensions_total,
            "debts": Decimal("0"),
            "credit_cards": credit_card_liabilities + cards_total,
        },
    }


def build_monthly_cash_flow_for_range(user, start_date, end_date) -> dict:
    """Build cash flow for an arbitrary date range (exclusive end)."""
    transactions = Transaction.objects.filter(
        Q(account__connection__user=user) | Q(card__connection__user=user),
        booked_at__gte=start_date,
        booked_at__lt=end_date,
    )

    income = transactions.filter(type=TransactionType.CREDIT).aggregate(total=Sum("amount")).get(
        "total"
    ) or Decimal("0")
    expenses = transactions.filter(type=TransactionType.DEBIT).aggregate(total=Sum("amount")).get(
        "total"
    ) or Decimal("0")

    subscription_expenses = Subscription.objects.filter(
        user=user,
        is_active=True,
        payments__due_date__gte=start_date,
        payments__due_date__lt=end_date,
        payments__status__in=("paid", "overdue"),
    ).aggregate(total=Sum("amount")).get("total") or Decimal("0")

    total_expenses = expenses + subscription_expenses
    savings = income - total_expenses
    savings_rate = (savings / income * Decimal("100")) if income > 0 else Decimal("0")

    return {
        "income": income,
        "expenses": total_expenses,
        "savings": savings,
        "savings_rate": savings_rate,
    }


def build_monthly_cash_flow(user, year: int, month: int) -> dict:
    start = date_type(year, month, 1)
    if month == 12:
        end = date_type(year + 1, 1, 1)
    else:
        end = date_type(year, month + 1, 1)

    flow = build_monthly_cash_flow_for_range(user, start, end)

    return {
        "year": year,
        "month": month,
        "income": flow["income"],
        "expenses": flow["expenses"],
        "savings": flow["savings"],
        "savings_rate": flow["savings_rate"],
    }


def _first_day_of_next_month(reference: date_type) -> date_type:
    if reference.month == 12:
        return date_type(reference.year + 1, 1, 1)
    return date_type(reference.year, reference.month + 1, 1)


def _payment_amount(payment: SubscriptionPayment) -> Decimal:
    """Valor a considerar para um pagamento.

    Pago usa o valor que realmente saiu da conta -- consumo de agua e luz varia,
    e o esperado cadastrado seria ficcao. Marcacao manual nao exige informar
    valor, entao cai no esperado.
    """
    if payment.status == SubscriptionStatus.PAID and payment.paid_amount is not None:
        return payment.paid_amount
    return payment.subscription.amount


def build_subscription_overview(
    user, today: date_type | None = None, upcoming_days: int = 30
) -> dict:
    """Consolida assinaturas para o dashboard: quanto compromete, o que atrasou,
    o que vence em seguida.

    Escopado a assinaturas ativas: uma assinatura cancelada com pendencia antiga
    continuaria pedindo atencao para sempre.
    """
    reference = today or date.today()
    horizon = reference + timedelta(days=upcoming_days)
    month_start = reference.replace(day=1)
    month_end = _first_day_of_next_month(reference)

    active = Subscription.objects.filter(user=user, is_active=True)
    monthly_recurring_total = active.aggregate(total=Sum("amount")).get("total") or Decimal("0")

    # Uma query para todos os pagamentos relevantes; o resto e agrupamento em
    # memoria. A view roda a cada carga do dashboard, entao o custo tem de ser
    # fixo e nao uma query por assinatura.
    payments = list(
        SubscriptionPayment.objects.filter(
            subscription__user=user,
            subscription__is_active=True,
        )
        .filter(Q(due_date__gte=month_start) | Q(status=SubscriptionStatus.OVERDUE))
        .select_related("subscription")
        .order_by("due_date")
    )

    def as_item(payment: SubscriptionPayment) -> dict:
        return {
            "name": payment.subscription.name,
            "category": payment.subscription.category,
            "due_date": payment.due_date,
            "amount": _payment_amount(payment),
            "status": payment.status,
        }

    overdue = [as_item(p) for p in payments if p.status == SubscriptionStatus.OVERDUE]
    upcoming = [
        as_item(p)
        for p in payments
        if p.status == SubscriptionStatus.PENDING and reference <= p.due_date <= horizon
    ]

    in_month = [p for p in payments if month_start <= p.due_date < month_end]
    paid_this_month = sum(
        (_payment_amount(p) for p in in_month if p.status == SubscriptionStatus.PAID),
        Decimal("0"),
    )
    pending_this_month = sum(
        (
            _payment_amount(p)
            for p in in_month
            if p.status in (SubscriptionStatus.PENDING, SubscriptionStatus.OVERDUE)
        ),
        Decimal("0"),
    )

    return {
        "monthly_recurring_total": monthly_recurring_total,
        "active_count": active.count(),
        "paid_this_month": paid_this_month,
        "pending_this_month": pending_this_month,
        "overdue_total": sum((item["amount"] for item in overdue), Decimal("0")),
        "overdue": overdue,
        "upcoming": upcoming,
    }


def add_months(reference: date_type, months: int) -> date_type:
    """Soma meses de calendario, preservando o dia quando o mes destino permite.

    `reference + timedelta(days=months * 30)` erra cada vez mais conforme o
    horizonte cresce: em 120 meses a diferenca passa de dois meses.
    """
    total = reference.month - 1 + months
    year = reference.year + total // 12
    month = total % 12 + 1
    day = min(reference.day, calendar.monthrange(year, month)[1])
    return date_type(year, month, day)


def previous_month_keys(reference: date_type, count: int) -> list[tuple[int, int]]:
    """Os `count` meses de calendario anteriores a `reference`, do mais recente ao
    mais antigo.

    Existe porque `reference - timedelta(days=30 * i)` erra: a partir de 31/03 isso
    cai em 01/03 -- o mesmo mes -- contando marco duas vezes e pulando fevereiro.
    """
    keys = []
    year, month = reference.year, reference.month
    for _ in range(count):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        keys.append((year, month))
    return keys


def build_recent_month_averages(user, months: int = 3, today: date_type | None = None) -> dict:
    """Media de receita, despesa e poupanca dos ultimos meses fechados.

    Uma leitura por mes. A projecao de liberdade financeira calculava a media de
    poupanca e a de despesa em lacos separados sobre os mesmos meses, dobrando o
    custo (6 chamadas de `build_monthly_cash_flow` onde 3 bastam).
    """
    reference = today or date.today()
    flows = [
        build_monthly_cash_flow(user, year=year, month=month)
        for year, month in previous_month_keys(reference, months)
    ]
    if not flows:
        return {"income": Decimal("0"), "expenses": Decimal("0"), "savings": Decimal("0")}

    divisor = Decimal(len(flows))
    totals = {"income": Decimal("0"), "expenses": Decimal("0"), "savings": Decimal("0")}
    for flow in flows:
        for key in totals:
            totals[key] += flow[key]
    return {key: value / divisor for key, value in totals.items()}


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
