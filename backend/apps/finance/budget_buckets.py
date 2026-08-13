"""Otimizador automatico de financas: guidance-only.

Compara o quanto da renda do mes foi para cada bucket de orcamento (despesas
fixas, investimentos, reserva de emergencia, metas, discricionario) contra o
alvo definido pelo usuario. Nunca move dinheiro nem inicia pagamento -- o app
nao tem integracao de pagamentos, so leitura via Pluggy. A saida e orientacao e
um alerta derivado (`alerts._budget_bucket_alerts`) quando um bucket fica
consistentemente fora do alvo.
"""

from datetime import date as date_type
from datetime import datetime, time
from decimal import Decimal

from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from .consolidation import add_months, build_monthly_cash_flow, exclude_internal_transfers
from .models import (
    BudgetBucket,
    BudgetBucketTarget,
    FinanceTag,
    FinanceTagKind,
    SubscriptionPayment,
    SubscriptionStatus,
    Transaction,
    TransactionType,
)


def classify_transaction_bucket(category: str) -> str:
    """Bucket de gasto (fixas x discricionario) por categoria normalizada.

    Investimentos/reserva/metas nao entram aqui: sao reconhecidos por destino
    (credito numa conta tagueada, ver `_tagged_account_credits_for_month`), nao
    por categoria de transacao -- categoria diz o que foi comprado, nao pra
    onde o dinheiro guardado foi.
    """
    if category in settings.FINANCE_FIXED_EXPENSE_CATEGORIES:
        return BudgetBucket.FIXED_EXPENSES
    return BudgetBucket.DISCRETIONARY


def _owned_by(user):
    """`Transaction` filtrado por dono via conta OU cartao -- mesmo par de `Q`
    usado em `consolidation.py`, extraido para nao repetir a cada query deste
    modulo."""
    return Q(account__connection__user=user) | Q(card__connection__user=user)


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = date_type(year, month, 1)
    end = add_months(start, 1)
    return (
        timezone.make_aware(datetime.combine(start, time.min)),
        timezone.make_aware(datetime.combine(end, time.min)),
    )


def _subscription_fixed_expenses(user, year: int, month: int) -> Decimal:
    """Assinaturas pagas no mes -- sempre despesa fixa, qualquer que seja a
    categoria da transacao que a liquidou (Netflix cai em "Lazer" na
    categorizacao de transacao, mas e um compromisso fixo, nao discricionario).
    """
    payments = SubscriptionPayment.objects.filter(
        subscription__user=user,
        due_date__year=year,
        due_date__month=month,
        status=SubscriptionStatus.PAID,
    ).select_related("subscription")
    total = Decimal("0")
    for payment in payments:
        total += (
            payment.paid_amount if payment.paid_amount is not None else payment.subscription.amount
        )
    return total


def _matched_subscription_transaction_ids(user, year: int, month: int) -> set[int]:
    """Transacoes ja contadas como assinatura em `_subscription_fixed_expenses`.

    Excluidas do debito por categoria abaixo para o mesmo gasto nao entrar
    tambem como discricionario (ex.: Netflix contaria em "Lazer" e de novo
    aqui).
    """
    return set(
        SubscriptionPayment.objects.filter(
            subscription__user=user,
            due_date__year=year,
            due_date__month=month,
            status=SubscriptionStatus.PAID,
            matched_transaction__isnull=False,
        ).values_list("matched_transaction_id", flat=True)
    )


def _tagged_account_credits_for_month(
    user, start_at: datetime, end_at: datetime
) -> dict[str, Decimal]:
    """Credito recebido em contas tagueadas por bucket, no mes.

    E o sinal de investimentos/reserva/metas: dinheiro que chegou numa conta
    marcada para aquele fim. Transferencia entre contas proprias entra de
    proposito (e exatamente o aporte que se quer medir) -- diferente do fluxo
    de caixa, que exclui essas transacoes por nao serem receita real.
    """
    tags = FinanceTag.objects.filter(
        user=user, kind=FinanceTagKind.BUDGET_BUCKET, account__isnull=False
    ).select_related("account")

    totals: dict[str, Decimal] = {}
    for tag in tags:
        credited = Transaction.objects.filter(
            account=tag.account,
            type=TransactionType.CREDIT,
            booked_at__gte=start_at,
            booked_at__lt=end_at,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if credited:
            totals[tag.value] = totals.get(tag.value, Decimal("0")) + credited
    return totals


def build_bucket_actuals_for_month(user, year: int, month: int) -> dict[str, Decimal]:
    """Valor realizado por bucket no mes, pronto para comparar com a renda."""
    start_at, end_at = _month_bounds(year, month)
    totals: dict[str, Decimal] = {bucket: Decimal("0") for bucket in BudgetBucket.values}

    matched_subscription_ids = _matched_subscription_transaction_ids(user, year, month)
    debit_queryset = exclude_internal_transfers(
        Transaction.objects.filter(
            _owned_by(user),
            type=TransactionType.DEBIT,
            booked_at__gte=start_at,
            booked_at__lt=end_at,
        )
    ).exclude(id__in=matched_subscription_ids)

    for row in debit_queryset.values("category").annotate(total=Sum("amount")):
        bucket = classify_transaction_bucket(row["category"] or "")
        totals[bucket] += row["total"] or Decimal("0")

    totals[BudgetBucket.FIXED_EXPENSES] += _subscription_fixed_expenses(user, year, month)

    for bucket, amount in _tagged_account_credits_for_month(user, start_at, end_at).items():
        if bucket in totals:
            totals[bucket] += amount

    return totals


def build_bucket_drift(user, year: int, month: int) -> list[dict]:
    """Alvo x realizado por bucket, os dois como % da renda do mes.

    Denominador e a renda (nao a soma dos buckets): a pergunta que este
    otimizador responde e "de cada real que entrou, quanto foi pra onde" --
    mesma moldura do prompt original ("55% despesas fixas / 25% investimentos
    / ..."). Sem renda no mes, tudo fica em 0% (nao ha o que dividir).
    """
    targets = {
        target.bucket: target.target_percentage
        for target in BudgetBucketTarget.objects.filter(user=user)
    }
    actual = build_bucket_actuals_for_month(user, year, month)
    income = build_monthly_cash_flow(user, year=year, month=month)["income"]

    rows: list[dict] = []
    for bucket in BudgetBucket.values:
        target_pct = targets.get(bucket, Decimal("0"))
        amount = actual.get(bucket, Decimal("0"))
        actual_pct = (amount / income * Decimal("100")) if income > 0 else Decimal("0")
        rows.append(
            {
                "bucket": bucket,
                "label": BudgetBucket(bucket).label,
                "target_percentage": target_pct,
                "actual_percentage": actual_pct,
                "actual_amount": amount,
                "drift_pp": actual_pct - target_pct,
            }
        )
    rows.sort(key=lambda row: -row["target_percentage"])
    return rows


def serialize_bucket_drift(rows: list[dict]) -> list[dict]:
    """Forma JSON-segura (float) de `build_bucket_drift` -- mesmo raciocinio de
    `allocation.serialize_allocation_drift`."""
    return [
        {
            "bucket": row["bucket"],
            "label": row["label"],
            "target_percentage": float(row["target_percentage"]),
            "actual_percentage": float(row["actual_percentage"]),
            "actual_amount": float(row["actual_amount"]),
            "drift_pp": float(row["drift_pp"]),
        }
        for row in rows
    ]
