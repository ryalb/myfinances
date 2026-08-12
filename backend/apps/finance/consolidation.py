import calendar
from datetime import date, datetime, time, timedelta
from datetime import date as date_type
from decimal import Decimal
from typing import TypedDict

from django.conf import settings
from django.db.models import Q, Sum
from django.db.models.functions import Lower
from django.utils import timezone

from .domain import classify_account_balance
from .models import (
    Account,
    Card,
    FinancialGoal,
    GoalStatus,
    InvestmentPosition,
    MonthlyReview,
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
    pensions = PensionPlan.objects.filter(user=user)
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


def _exclude_internal_transfers(queryset):
    """Remove transferencias internas (fatura de cartao, transferencia entre
    contas proprias) de um queryset de `Transaction`.

    Extraido daqui porque a mesma exclusao passou a ser necessaria em mais de um
    lugar (fluxo de caixa, deltas de categoria da revisao mensal): repetir o
    annotate+exclude arrisca a lista de categorias divergir entre eles.
    """
    return queryset.annotate(provider_category_lower=Lower("provider_category")).exclude(
        provider_category_lower__in=settings.FINANCE_INTERNAL_TRANSFER_CATEGORIES
    )


def build_monthly_cash_flow_for_range(user, start_date, end_date) -> dict:
    """Build cash flow for an arbitrary date range (exclusive end)."""
    # `booked_at` e DateTimeField; filtrar com um `date` cru promove para meia-
    # noite **naive** e o Django avisa (e assume UTC) a cada chamada -- aware de
    # proposito, no fuso ativo, para o limite do dia bater com o que a tela mostra.
    start_at = timezone.make_aware(datetime.combine(start_date, time.min))
    end_at = timezone.make_aware(datetime.combine(end_date, time.min))

    # Pagamento de fatura de cartao chega da Pluggy como duas transacoes: debito
    # na conta (saida real) e credito no cartao (so abate a divida). Sem excluir
    # pela categoria, o lado do cartao virava receita fantasma e o lado da conta
    # duplicava uma despesa que ja foi contada quando a compra ocorreu no cartao.
    # O mesmo vale para transferencia entre contas do proprio usuario.
    transactions = _exclude_internal_transfers(
        Transaction.objects.filter(
            Q(account__connection__user=user) | Q(card__connection__user=user),
            booked_at__gte=start_at,
            booked_at__lt=end_at,
        )
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


def build_savings_rate_trend(user, year: int, month: int, months: int = 6) -> list[dict]:
    """Fluxo de caixa mensal dos `months` meses terminando em (year, month),
    incluido, do mais antigo ao mais recente -- ordem que a tela de revisao usa
    para desenhar a tendencia.
    """
    reference = date_type(year, month, 1)
    return [
        build_monthly_cash_flow(user, year=month_date.year, month=month_date.month)
        for month_date in (add_months(reference, -offset) for offset in reversed(range(months)))
    ]


class CategoryDelta(TypedDict):
    category: str
    current_amount: Decimal
    previous_amount: Decimal
    delta: Decimal


def build_category_deltas_for_month(user, year: int, month: int) -> list[CategoryDelta]:
    """Gasto por categoria do mes vs. o mes anterior, do maior aumento para o
    maior corte.

    Mesma exclusao de transferencias internas do fluxo de caixa: fatura de
    cartao e transferencia entre contas proprias inflam qualquer categoria em
    que cairem, sem ser gasto real.
    """
    current_start = date_type(year, month, 1)
    current_end = _first_day_of_next_month(current_start)
    previous_start = add_months(current_start, -1)
    previous_end = current_start

    def totals_by_category(start: date_type, end: date_type) -> dict[str, Decimal]:
        start_at = timezone.make_aware(datetime.combine(start, time.min))
        end_at = timezone.make_aware(datetime.combine(end, time.min))
        queryset = _exclude_internal_transfers(
            Transaction.objects.filter(
                Q(account__connection__user=user) | Q(card__connection__user=user),
                type=TransactionType.DEBIT,
                booked_at__gte=start_at,
                booked_at__lt=end_at,
            )
        )
        rows = queryset.values("category").annotate(total=Sum("amount"))
        return {(row["category"] or "sem categoria"): row["total"] or Decimal("0") for row in rows}

    current = totals_by_category(current_start, current_end)
    previous = totals_by_category(previous_start, previous_end)

    deltas: list[CategoryDelta] = []
    for category in set(current) | set(previous):
        current_amount = current.get(category, Decimal("0"))
        previous_amount = previous.get(category, Decimal("0"))
        deltas.append(
            {
                "category": category,
                "current_amount": current_amount,
                "previous_amount": previous_amount,
                "delta": current_amount - previous_amount,
            }
        )
    deltas.sort(key=lambda item: -item["delta"])
    return deltas


def build_monthly_review_summary(user, year: int, month: int) -> dict:
    """Compoe os dados do ritual de revisao mensal e garante a linha
    `MonthlyReview` do mes (criada vazia no primeiro acesso, mesmo idiom de
    `snapshot_net_worth`).

    Patrimonio, tendencia de poupanca e deltas de categoria sao sempre
    recalculados das tabelas fonte -- so `adjustments`/`completed_at` (input do
    usuario) persistem no `MonthlyReview` propriamente.
    """
    review, _ = MonthlyReview.objects.get_or_create(user=user, year=year, month=month)

    reference_date = date_type(year, month, 1)
    period_end = _first_day_of_next_month(reference_date)

    current_snapshot = (
        NetWorthSnapshot.objects.filter(user=user, date__lt=period_end).order_by("-date").first()
    )
    previous_snapshot = (
        NetWorthSnapshot.objects.filter(user=user, date__lt=reference_date)
        .order_by("-date")
        .first()
    )
    net_worth_delta = (
        current_snapshot.net_worth - previous_snapshot.net_worth
        if current_snapshot and previous_snapshot
        else None
    )

    savings_rate_trend = build_savings_rate_trend(user, year, month)
    category_deltas = build_category_deltas_for_month(user, year, month)

    achievements = []
    current_flow = savings_rate_trend[-1]
    averages = build_recent_month_averages(user, months=3, today=reference_date)
    if averages["income"] > 0:
        average_rate = averages["savings"] / averages["income"] * Decimal("100")
        if current_flow["savings_rate"] > average_rate:
            achievements.append(
                "Taxa de poupança do mês ficou acima da média dos últimos 3 meses."
            )

    # Heuristica de v1: `updated_at` e o unico timestamp que `FinancialGoal` tem
    # para "quando ficou concluida" -- qualquer outra edicao numa meta ja
    # concluida a traria de volta para a revisao daquele mes.
    achieved_goals = FinancialGoal.objects.filter(
        user=user,
        status=GoalStatus.ACHIEVED,
        updated_at__date__gte=reference_date,
        updated_at__date__lt=period_end,
    )
    achievements.extend(f'Meta "{goal.name}" foi concluída este mês.' for goal in achieved_goals)

    return {
        "review": review,
        "net_worth_delta": net_worth_delta,
        "current_net_worth": current_snapshot.net_worth if current_snapshot else None,
        "savings_rate_trend": savings_rate_trend,
        "category_deltas": category_deltas,
        "achievements": achievements,
    }
