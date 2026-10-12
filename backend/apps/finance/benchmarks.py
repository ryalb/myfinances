"""Rendimento acumulado de CDI e IPCA nas janelas da tela de investimentos.

E a regua do "ainda vale a pena?": um investimento que rende menos que o CDI
no mesmo periodo perde para a alternativa de risco quase zero. As janelas
(1, 3 e 12 meses) sao as mesmas que a tela mostra por ativo.

CDI (SGS 12) e taxa diaria em %, entao o acumulado e o produto de (1 + taxa)
dos dias uteis dentro da janela. IPCA (SGS 433) e variacao mensal publicada
com atraso, entao a janela e "ultimos N meses publicados", nao por data --
mesma convencao do "IPCA 12 meses" que o IBGE divulga.

Janela sem historico suficiente sai `None`, nao um acumulado parcial: um CDI
"de 12 meses" calculado com 2 meses de pontos pareceria muito baixo e faria
qualquer investimento parecer bom.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import MarketIndexKind, MarketIndexRate

WINDOW_DAYS = {"m1": 30, "m3": 91, "m12": 365}
WINDOW_MONTHS = {"m1": 1, "m3": 3, "m12": 12}

# Feriado prolongado/fim de semana no inicio da janela deixa alguns dias sem
# ponto de CDI; mais que isso e falta de historico salvo.
CDI_COVERAGE_TOLERANCE_DAYS = 5

BUSINESS_DAYS_PER_YEAR = 252

HUNDRED = Decimal("100")


def _accumulate(values: list[Decimal]) -> Decimal:
    factor = Decimal("1")
    for value in values:
        factor *= 1 + value / HUNDRED
    return (factor - 1) * HUNDRED


def cdi_accumulated(start: date, end: date) -> Decimal | None:
    oldest = (
        MarketIndexRate.objects.filter(kind=MarketIndexKind.CDI)
        .order_by("reference_date")
        .values_list("reference_date", flat=True)
        .first()
    )
    if oldest is None or oldest > start + timedelta(days=CDI_COVERAGE_TOLERANCE_DAYS):
        return None
    values = list(
        MarketIndexRate.objects.filter(
            kind=MarketIndexKind.CDI, reference_date__gt=start, reference_date__lte=end
        )
        .order_by("reference_date")
        .values_list("value", flat=True)
    )
    if not values:
        return None
    return _accumulate(values)


def cdi_annual_rate() -> tuple[Decimal | None, date | None]:
    """Taxa diaria mais recente anualizada em 252 dias uteis (convencao B3)."""
    latest = (
        MarketIndexRate.objects.filter(kind=MarketIndexKind.CDI).order_by("-reference_date").first()
    )
    if latest is None:
        return None, None
    annual = ((1 + latest.value / HUNDRED) ** BUSINESS_DAYS_PER_YEAR - 1) * HUNDRED
    return annual, latest.reference_date


def ipca_accumulated(months: int) -> Decimal | None:
    values = list(
        MarketIndexRate.objects.filter(kind=MarketIndexKind.IPCA)
        .order_by("-reference_date")
        .values_list("value", flat=True)[:months]
    )
    if len(values) < months:
        return None
    return _accumulate(values)


def build_market_benchmarks(
    today: date | None = None, since_dates: list[date] | None = None
) -> dict:
    """`since_dates` sao datas de compra: o CDI acumulado de cada uma ate hoje
    e a comparacao justa para o rendimento "desde a compra", em vez da taxa
    atual anualizada (o CDI de 2 anos atras pode ser bem diferente do de hoje).
    """
    today = today or timezone.localdate()
    cdi_annual, cdi_as_of = cdi_annual_rate()
    ipca_as_of = (
        MarketIndexRate.objects.filter(kind=MarketIndexKind.IPCA)
        .order_by("-reference_date")
        .values_list("reference_date", flat=True)
        .first()
    )
    return {
        "cdi": {
            "as_of": cdi_as_of,
            "annual_rate": cdi_annual,
            **{
                key: cdi_accumulated(today - timedelta(days=days), today)
                for key, days in WINDOW_DAYS.items()
            },
        },
        "ipca": {
            "as_of": ipca_as_of,
            **{key: ipca_accumulated(months) for key, months in WINDOW_MONTHS.items()},
        },
        "cdi_since": [
            {"date": since, "value": cdi_accumulated(since, today)}
            for since in sorted(set(since_dates or []))
            if since < today
        ],
    }
