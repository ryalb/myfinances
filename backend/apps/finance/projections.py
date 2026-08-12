"""Projecao de patrimonio de longo prazo.

Complementa `resolve_financial_freedom_projection` (graphql.py), que resolve "em
quantos meses chego a 25x a despesa anual" para uma taxa fixa -- uma projecao de
*tempo-at-meta*. Este modulo resolve o problema complementar, *valor-no-horizonte*:
"quanto terei em 5/10/20 anos", em varios cenarios, mais um cenario de estresse e
os ajustes que mais mudariam o resultado (leverage points).
"""

from datetime import date
from decimal import Decimal
from typing import TypedDict

from django.conf import settings

from .consolidation import build_recent_month_averages, build_user_financial_summary
from .models import FinancialGoal, GoalStatus

# Mesmas taxas usadas por `resolve_financial_freedom_projection` (graphql.py) --
# unica fonte de verdade, para as duas projecoes nunca discordarem sobre o que e
# uma carteira conservadora/base/agressiva.
DEFAULT_SCENARIO_RATES = {
    "conservative": Decimal("0.04"),
    "base": Decimal("0.08"),
    "aggressive": Decimal("0.12"),
}

HORIZONS_YEARS = (5, 10, 20)

# Choque de mercado e hiato de renda do cenario de estresse (config/settings.py,
# mesmo idiom env-overridable de FINANCE_INTERNAL_TRANSFER_CATEGORIES).
STRESS_MARKET_DROP_PCT = Decimal(settings.FINANCE_STRESS_MARKET_DROP_PCT) / Decimal(100)
STRESS_INCOME_GAP_MONTHS = int(settings.FINANCE_STRESS_INCOME_GAP_MONTHS)


class LeverageCandidate(TypedDict, total=False):
    key: str
    label: str
    savings_delta_pct: Decimal
    rate_delta: Decimal


class LeveragePoint(TypedDict):
    key: str
    label: str
    projected_net_worth: Decimal
    impact: Decimal


# Ajustes candidatos avaliados por `build_leverage_points`. Enumeracao fixa e
# nao um otimizador: cada candidato e recalculado contra o cenario base e os de
# maior impacto vencem -- nunca uma busca livre por "o melhor ajuste possivel".
# TypedDict (nao um dict literal comum) para que `candidate["savings_delta_pct"]`
# tipe como `Decimal`, e nao como a uniao `str | Decimal` que o dict misturando
# "key"/"label" (str) com os deltas (Decimal) produziria.
LEVERAGE_CANDIDATES: tuple[LeverageCandidate, ...] = (
    {
        "key": "savings_rate_plus_5pp",
        "label": "Aumentar a poupança mensal em 5 p.p. da renda",
        "savings_delta_pct": Decimal("0.05"),
    },
    {
        "key": "savings_rate_plus_10pp",
        "label": "Aumentar a poupança mensal em 10 p.p. da renda",
        "savings_delta_pct": Decimal("0.10"),
    },
    {
        "key": "return_plus_2pp",
        "label": "Buscar uma carteira com +2 p.p. de retorno anual",
        "rate_delta": Decimal("0.02"),
    },
    {
        "key": "return_plus_4pp",
        "label": "Buscar uma carteira com +4 p.p. de retorno anual",
        "rate_delta": Decimal("0.04"),
    },
)

LEVERAGE_HORIZON_MONTHS = 20 * 12
LEVERAGE_TOP_N = 3


def project_net_worth_at_horizon(
    current_net_worth: Decimal, monthly_contribution: Decimal, annual_rate: Decimal, months: int
) -> Decimal:
    """Valor futuro com aporte mensal constante.

    `FV = PV*(1+r)^n + PMT*(((1+r)^n - 1) / r)`, `r` = taxa mensal. Aporte
    negativo (retirada) e permitido -- usado pelo cenario de estresse durante o
    hiato de renda, onde o gasto continua sem entrada de dinheiro.
    """
    if months <= 0:
        return current_net_worth
    monthly_rate = annual_rate / Decimal(12)
    growth = (Decimal(1) + monthly_rate) ** months
    future_value = current_net_worth * growth
    if monthly_rate == 0:
        future_value += monthly_contribution * Decimal(months)
    else:
        future_value += monthly_contribution * ((growth - Decimal(1)) / monthly_rate)
    return future_value


def project_stress_scenario(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    annual_rate: Decimal,
    months: int,
    *,
    shock_pct: Decimal = STRESS_MARKET_DROP_PCT,
    income_gap_months: int = STRESS_INCOME_GAP_MONTHS,
) -> Decimal:
    """Choque de mercado hoje + hiato de renda logo no inicio, depois retomada normal.

    Simplificacao deliberada de v1: os dois golpes acontecem juntos no inicio do
    horizonte (pior caso simultaneo) em vez de numa data aleatoria no meio do
    caminho -- suficiente para medir sensibilidade sem ter que escolher (ou expor
    ao usuario) uma data de choque arbitraria.
    """
    if months <= 0:
        return current_net_worth
    shocked_net_worth = current_net_worth * (Decimal(1) - shock_pct)
    gap_months = min(income_gap_months, months)
    after_gap = project_net_worth_at_horizon(
        shocked_net_worth, Decimal("0"), annual_rate, gap_months
    )
    remaining_months = months - gap_months
    return project_net_worth_at_horizon(
        after_gap, monthly_contribution, annual_rate, remaining_months
    )


def build_leverage_points(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    monthly_income: Decimal,
    base_rate: Decimal,
    months: int = LEVERAGE_HORIZON_MONTHS,
    top_n: int = LEVERAGE_TOP_N,
) -> list[LeveragePoint]:
    """Reavalia cada ajuste candidato contra o cenario base de 20 anos.

    Sem renda media (usuario novo, sem historico de 3 meses) os candidatos de
    taxa de poupanca nao tem "renda" para aplicar o p.p. em cima e sao pulados --
    os de retorno assumido continuam validos independente disso.
    """
    base_value = project_net_worth_at_horizon(
        current_net_worth, monthly_contribution, base_rate, months
    )

    points: list[LeveragePoint] = []
    for candidate in LEVERAGE_CANDIDATES:
        savings_delta_pct = candidate.get("savings_delta_pct")
        if savings_delta_pct is not None:
            if monthly_income <= 0:
                continue
            adjusted_contribution = monthly_contribution + monthly_income * savings_delta_pct
            adjusted_rate = base_rate
        else:
            adjusted_contribution = monthly_contribution
            adjusted_rate = base_rate + candidate["rate_delta"]

        adjusted_value = project_net_worth_at_horizon(
            current_net_worth, adjusted_contribution, adjusted_rate, months
        )
        points.append(
            {
                "key": candidate["key"],
                "label": candidate["label"],
                "projected_net_worth": adjusted_value,
                "impact": adjusted_value - base_value,
            }
        )

    points.sort(key=lambda point: -point["impact"])
    return points[:top_n]


def _months_between(start: date, end: date) -> int:
    """Meses de calendario entre duas datas (aproximado ao mes, nao ao dia).

    Suficiente para uma projecao de anos: a diferenca de alguns dias no mes de
    corte nao muda o resultado de forma perceptivel num horizonte tao longo.
    """
    return (end.year - start.year) * 12 + (end.month - start.month)


def _build_goal_viability(
    user, monthly_contribution: Decimal, base_rate: Decimal, today: date | None = None
) -> list[dict]:
    """Viabilidade de cada meta ativa com data-alvo.

    Compara contra o *crescimento projetado* (quanto a poupanca media, a juros
    compostos, acumularia entre hoje e a data-alvo) e nao contra o patrimonio
    total: nao ha hoje contribuicao por meta, entao comparar uma meta pequena
    (ex.: viagem de R$8.000) contra o patrimonio total do usuario diria "on
    track" para qualquer meta positiva, o que nao informa nada. O que a meta
    realmente precisa e cobrir a diferenca entre o que já tem (`current_amount`)
    e o alvo -- e essa diferenca e o que se compara ao crescimento projetado.
    """
    reference = today or date.today()
    goals = FinancialGoal.objects.filter(
        user=user, status=GoalStatus.ACTIVE, target_date__isnull=False
    ).order_by("target_date")

    results = []
    for goal in goals:
        months = _months_between(reference, goal.target_date)
        remaining_needed = max(Decimal("0"), goal.target_amount - goal.current_amount)
        projected_growth = (
            project_net_worth_at_horizon(Decimal("0"), monthly_contribution, base_rate, months)
            if months > 0
            else Decimal("0")
        )
        results.append(
            {
                "id": goal.id,
                "name": goal.name,
                "target_amount": goal.target_amount,
                "target_date": goal.target_date,
                "on_track": projected_growth >= remaining_needed,
                "shortfall": max(Decimal("0"), remaining_needed - projected_growth),
                "projected_growth": projected_growth,
                "remaining_needed": remaining_needed,
            }
        )
    return results


def build_future_projection(user, horizons: tuple[int, ...] = HORIZONS_YEARS) -> dict:
    """Projecao completa: cenarios x horizontes, estresse, leverage points e metas.

    Aporte mensal medio vem de `build_recent_month_averages` (ultimos 3 meses),
    a mesma janela usada por `resolve_financial_freedom_projection` -- as duas
    projecoes partem da mesma base de poupanca, so divergem no que perguntam.
    """
    summary = build_user_financial_summary(user)
    current_net_worth = summary["net_worth"]

    averages = build_recent_month_averages(user, months=3)
    monthly_contribution = averages["savings"]
    monthly_income = averages["income"]

    scenarios = {
        name: {
            years: project_net_worth_at_horizon(
                current_net_worth, monthly_contribution, rate, years * 12
            )
            for years in horizons
        }
        for name, rate in DEFAULT_SCENARIO_RATES.items()
    }

    base_rate = DEFAULT_SCENARIO_RATES["base"]
    stress = {
        years: project_stress_scenario(
            current_net_worth, monthly_contribution, base_rate, years * 12
        )
        for years in horizons
    }

    leverage_points = build_leverage_points(
        current_net_worth, monthly_contribution, monthly_income, base_rate
    )

    goals = _build_goal_viability(user, monthly_contribution, base_rate)

    return {
        "current_net_worth": current_net_worth,
        "monthly_contribution": monthly_contribution,
        "horizons": list(horizons),
        "scenarios": scenarios,
        "stress": stress,
        "leverage_points": leverage_points,
        "goals": goals,
    }


def serialize_future_projection(data: dict) -> dict:
    """Forma JSON-segura (float/str/isoformat) do payload de `build_future_projection`.

    Um unico lugar convertendo Decimal/date para o que a fronteira aceita --
    reaproveitado pela persistencia (`FutureProjectionReport.projection`), pela
    resposta da view de IA e pelo resolver GraphQL, para os tres nunca divergirem
    em como arredondam ou formatam o mesmo numero.
    """
    return {
        "current_net_worth": float(data["current_net_worth"]),
        "monthly_contribution": float(data["monthly_contribution"]),
        "horizons": list(data["horizons"]),
        "scenarios": {
            name: {str(years): float(value) for years, value in series.items()}
            for name, series in data["scenarios"].items()
        },
        "stress": {str(years): float(value) for years, value in data["stress"].items()},
        "leverage_points": [
            {
                "key": point["key"],
                "label": point["label"],
                "projected_net_worth": float(point["projected_net_worth"]),
                "impact": float(point["impact"]),
            }
            for point in data["leverage_points"]
        ],
        "goals": [
            {
                "id": goal["id"],
                "name": goal["name"],
                "target_amount": float(goal["target_amount"]),
                "target_date": goal["target_date"].isoformat() if goal["target_date"] else None,
                "on_track": goal["on_track"],
                "shortfall": float(goal["shortfall"]),
                "projected_growth": float(goal["projected_growth"]),
                "remaining_needed": float(goal["remaining_needed"]),
            }
            for goal in data["goals"]
        ],
    }
