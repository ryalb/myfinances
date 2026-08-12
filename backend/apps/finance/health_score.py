"""Diagnostico de saude financeira: nota 0-100 e as 3 acoes que mais ajudariam.

Sem model novo, no mesmo espirito de `alerts.py`: nada aqui e persistido, tudo e
recalculado das tabelas fonte a cada consulta. Cinco componentes, cada um com
faixas deterministicas (nunca um score continuo arbitrario), ponderados de forma
que os pesos somem exatamente 100 -- a soma ponderada dos componentes ja cai na
escala 0-100 sem normalizacao extra.
"""

from datetime import date
from decimal import Decimal
from typing import TypedDict

from django.db.models import Sum

from .alerts import build_user_alerts
from .consolidation import (
    add_months,
    build_recent_month_averages,
    build_user_financial_summary,
)
from .models import Card, NetWorthSnapshot


class HealthScoreComponent(TypedDict):
    key: str
    label: str
    score: Decimal
    weight: Decimal
    detail: str


# Os pesos somam 100: a soma ponderada dos componentes ja e a nota final, sem
# precisar dividir por um total separado.
COMPONENT_WEIGHTS = {
    "savings_rate": Decimal("30"),
    "emergency_fund": Decimal("25"),
    "credit_utilization": Decimal("20"),
    "net_worth_trend": Decimal("15"),
    "alerts": Decimal("10"),
}

# Frase de acao fixa por componente -- nao gerada, para nunca inventar um
# conselho que nao corresponde ao motivo real da nota baixa.
ACTION_TEXT = {
    "savings_rate": (
        "Aumente sua taxa de poupança: revise gastos recorrentes e direcione "
        "a diferença para investimentos."
    ),
    "emergency_fund": (
        "Priorize a reserva de emergência até cobrir de 3 a 6 meses de despesas."
    ),
    "credit_utilization": (
        "Reduza o saldo usado do cartão de crédito para abaixo de 30% do limite."
    ),
    "net_worth_trend": (
        "Investigue por que o patrimônio caiu nos últimos 3 meses e ajuste o orçamento."
    ),
    "alerts": (
        "Resolva os alertas ativos (pagamentos atrasados, conexões com erro) antes "
        "que piorem."
    ),
}


def _savings_rate_score(user, today: date | None = None) -> tuple[Decimal, str]:
    averages = build_recent_month_averages(user, months=3, today=today)
    # Sem renda no periodo, a taxa fica 0 e cai na faixa mais baixa -- nao ha
    # como demonstrar habito de poupanca sem historico de renda.
    rate = (
        averages["savings"] / averages["income"] * Decimal("100")
        if averages["income"] > 0
        else Decimal("0")
    )
    if rate >= 20:
        score = Decimal("100")
    elif rate >= 10:
        score = Decimal("70")
    elif rate >= 0:
        score = Decimal("40")
    else:
        score = Decimal("0")
    return score, f"Taxa de poupança média dos últimos 3 meses: {rate:.1f}%."


def _emergency_fund_score(user, today: date | None = None) -> tuple[Decimal, str]:
    summary = build_user_financial_summary(user)
    averages = build_recent_month_averages(user, months=3, today=today)
    cash = summary["breakdown"]["cash"]
    monthly_expenses = averages["expenses"]
    # Sem despesa media para dividir, trata como cobertura alta -- mesmo
    # sentinela usado em `financial_runway_months` (graphql.py) para "sem
    # despesa, sem o que descontar do caixa".
    months_covered = cash / monthly_expenses if monthly_expenses > 0 else Decimal("999")

    if months_covered >= 6:
        score = Decimal("100")
    elif months_covered >= 3:
        score = Decimal("70")
    elif months_covered >= 1:
        score = Decimal("40")
    else:
        score = Decimal("0")
    display_months = min(months_covered, Decimal("99"))
    return score, f"Caixa cobre {display_months:.1f} mês(es) de despesas."


def _credit_utilization_score(user) -> tuple[Decimal, str]:
    totals = Card.objects.filter(connection__user=user).aggregate(
        balance=Sum("current_balance"), limit=Sum("credit_limit")
    )
    balance = totals["balance"] or Decimal("0")
    limit = totals["limit"] or Decimal("0")
    # Sem limite de cartao (nenhum cartao sincronizado), nao ha divida
    # rotativa a penalizar -- utilizacao 0 cai na faixa mais alta.
    utilization = balance / limit * Decimal("100") if limit > 0 else Decimal("0")

    if utilization <= 30:
        score = Decimal("100")
    elif utilization <= 50:
        score = Decimal("70")
    elif utilization <= 80:
        score = Decimal("40")
    else:
        score = Decimal("0")
    return score, f"{utilization:.1f}% do limite de crédito em uso."


def _net_worth_trend_score(user, today: date | None = None) -> tuple[Decimal, str]:
    reference = today or date.today()
    cutoff = add_months(reference, -3)
    latest = (
        NetWorthSnapshot.objects.filter(user=user, date__lte=reference)
        .order_by("-date")
        .first()
    )
    baseline = (
        NetWorthSnapshot.objects.filter(user=user, date__lte=cutoff).order_by("-date").first()
    )

    # Menos de dois pontos separados por ~3 meses: nao ha tendencia para
    # calcular. Neutro (50), nao 0 -- falta de historico nao e o mesmo que
    # patrimonio em queda.
    if not latest or not baseline or latest.pk == baseline.pk:
        return Decimal("50"), "Histórico de patrimônio insuficiente para calcular a tendência."

    if baseline.net_worth == 0:
        change_pct = Decimal("100") if latest.net_worth > 0 else Decimal("0")
    else:
        change_pct = (
            (latest.net_worth - baseline.net_worth) / abs(baseline.net_worth) * Decimal("100")
        )

    if change_pct >= 5:
        score = Decimal("100")
    elif change_pct >= 0:
        score = Decimal("70")
    elif change_pct >= -10:
        score = Decimal("40")
    else:
        score = Decimal("0")
    return score, f"Patrimônio variou {change_pct:+.1f}% nos últimos 3 meses."


def _alerts_score(user) -> tuple[Decimal, str]:
    alerts = build_user_alerts(user)
    danger_count = sum(1 for alert in alerts if alert["severity"] == "danger")
    warning_count = sum(1 for alert in alerts if alert["severity"] == "warning")
    # "info" nao penaliza -- e o mesmo nivel que `alerts.py` trata como aviso
    # sem acao necessaria (ex.: vencimento futuro).
    penalty = danger_count * Decimal("40") + warning_count * Decimal("20")
    score = max(Decimal("0"), Decimal("100") - penalty)
    return score, f"{len(alerts)} alerta(s) ativo(s) ({danger_count} grave(s))."


def build_top_actions(components: list[HealthScoreComponent], top_n: int = 3) -> list[str]:
    """As `top_n` acoes para os componentes de nota mais baixa.

    Empate mantem a ordem original da lista (peso decrescente): entre dois
    componentes com a mesma nota, prioriza o de maior peso. Componente com
    nota 100 nunca entra -- nao ha acao a sugerir para o que ja esta no teto.
    """
    ranked = sorted(components, key=lambda component: component["score"])
    return [
        ACTION_TEXT[component["key"]] for component in ranked[:top_n] if component["score"] < 100
    ]


def build_financial_health_score(user, today: date | None = None) -> dict:
    savings_score, savings_detail = _savings_rate_score(user, today=today)
    emergency_score, emergency_detail = _emergency_fund_score(user, today=today)
    utilization_score, utilization_detail = _credit_utilization_score(user)
    trend_score, trend_detail = _net_worth_trend_score(user, today=today)
    alerts_score, alerts_detail = _alerts_score(user)

    components: list[HealthScoreComponent] = [
        {
            "key": "savings_rate",
            "label": "Taxa de poupança",
            "score": savings_score,
            "weight": COMPONENT_WEIGHTS["savings_rate"],
            "detail": savings_detail,
        },
        {
            "key": "emergency_fund",
            "label": "Reserva de emergência",
            "score": emergency_score,
            "weight": COMPONENT_WEIGHTS["emergency_fund"],
            "detail": emergency_detail,
        },
        {
            "key": "credit_utilization",
            "label": "Uso do limite de crédito",
            "score": utilization_score,
            "weight": COMPONENT_WEIGHTS["credit_utilization"],
            "detail": utilization_detail,
        },
        {
            "key": "net_worth_trend",
            "label": "Tendência de patrimônio",
            "score": trend_score,
            "weight": COMPONENT_WEIGHTS["net_worth_trend"],
            "detail": trend_detail,
        },
        {
            "key": "alerts",
            "label": "Alertas ativos",
            "score": alerts_score,
            "weight": COMPONENT_WEIGHTS["alerts"],
            "detail": alerts_detail,
        },
    ]

    total_score = sum(
        (component["score"] * component["weight"] for component in components), Decimal("0")
    ) / Decimal("100")

    return {
        "score": total_score,
        "components": components,
        "top_actions": build_top_actions(components),
    }
