"""Concentracao da carteira por emissor, indexador e moeda -- primeira leva dos
"riscos invisiveis" do ebook educacional "Diagnostico de Carteira Inteligente"
(concentracao disfarcada, indexadores repetidos, excesso de Brasil).

So o calculo, a partir da posicao mais recente de cada `Investment` -- sem
view/endpoint ainda. Fica de fora desta leva o que o ebook tambem descreve mas
sem dado estruturado suficiente hoje: liquidez/prazo (precisaria de um
horizonte por meta em `FinancialGoal`) e conflito produto x planejamento (e um
processo de consultoria, nao um calculo sobre os dados que temos).
"""

from collections.abc import Callable
from decimal import Decimal
from typing import TypedDict

from .consolidation import latest_positions_by_investment
from .models import Investment

UNKNOWN_LABEL = "Não informado"


class ConcentrationRow(TypedDict):
    key: str
    label: str
    amount: Decimal
    percentage: Decimal


class CurrencyExposure(TypedDict):
    brl_amount: Decimal
    brl_percentage: Decimal
    foreign_amount: Decimal
    foreign_percentage: Decimal
    by_currency: list[ConcentrationRow]


def _investment_values(user) -> list[tuple[Investment, Decimal]]:
    """Investimento e valor de mercado da posicao mais recente, para quem tem
    posicao com saldo (`market_value` zerado -- ex. resgate no mesmo dia da
    sincronizacao -- nao entra em nenhuma concentracao).
    """
    positions = latest_positions_by_investment(user)
    investments = Investment.objects.filter(connection__user=user)
    return [
        (investment, positions[investment.pk].market_value)
        for investment in investments
        if investment.pk in positions and positions[investment.pk].market_value
    ]


def _group_by(
    investment_values: list[tuple[Investment, Decimal]],
    key_fn: Callable[[Investment], str | None],
) -> list[ConcentrationRow]:
    """Agrupa por `key_fn(investment)` (`None`/vazio cai em `UNKNOWN_LABEL`) e
    calcula o percentual de cada grupo sobre a soma de `investment_values`.

    Para as tres funcoes `build_*` abaixo, essa soma e sempre o patrimonio
    investido total do usuario: toda posicao cai em algum grupo, nunca e
    descartada -- entao um "Não informado" grande e em si um dado util (ex.:
    quanto da carteira nao tem emissor identificavel).
    """
    totals: dict[str, Decimal] = {}
    for investment, amount in investment_values:
        key = key_fn(investment) or UNKNOWN_LABEL
        totals[key] = totals.get(key, Decimal("0")) + amount

    total = sum(totals.values(), Decimal("0")) or Decimal("1")
    rows: list[ConcentrationRow] = [
        {
            "key": key,
            "label": key,
            "amount": amount,
            "percentage": amount / total * Decimal("100"),
        }
        for key, amount in totals.items()
    ]
    rows.sort(key=lambda row: -row["amount"])
    return rows


def build_issuer_concentration(user) -> list[ConcentrationRow]:
    """Concentracao por emissor (risco de "concentracao disfarcada": varios
    CDBs de bancos diferentes, mas com risco de credito parecido).

    A Pluggy so manda `issuer` para renda fixa/credito -- Acoes, FIIs e ETF
    caem em `UNKNOWN_LABEL` de proposito, nao por erro: um "Não informado"
    grande sinaliza que boa parte da carteira nao tem emissor identificavel
    para avaliar risco de credito, o que tambem e diagnostico.
    """
    return _group_by(_investment_values(user), lambda inv: inv.issuer.strip() or None)


def build_indexer_concentration(user) -> list[ConcentrationRow]:
    """Concentracao por indexador (risco de "indexadores repetidos": CDB
    pos-fixado, fundo DI, Tesouro Selic e fundo de credito atrelado ao CDI tem
    nomes diferentes mas reagem igual ao mesmo ciclo de juros).

    Chave e `indexer_additional_info` (o indexador em si, ex. "CDI"/"IPCA") --
    `rate_type` (PRE/POS/FIXED) so entra como fallback quando a Pluggy nao
    manda o indexador, porque descreve a forma da taxa, nao a exposicao que
    este risco quer capturar.
    """
    return _group_by(
        _investment_values(user),
        lambda inv: inv.indexer_additional_info.strip() or inv.rate_type.strip() or None,
    )


def build_currency_exposure(user) -> CurrencyExposure:
    """Exposicao por moeda (risco de "excesso de Brasil": depender de uma
    unica moeda, pais e ciclo de juros).
    """
    by_currency = _group_by(_investment_values(user), lambda inv: inv.currency.strip() or None)

    # `total` real (sem carteira vazia entra como 0, nunca 1) -- a subtracao
    # abaixo depende disso; so a divisao de percentual usa o fallback seguro.
    total = sum((row["amount"] for row in by_currency), Decimal("0"))
    brl_amount = next(
        (row["amount"] for row in by_currency if row["key"] == "BRL"), Decimal("0")
    )
    foreign_amount = total - brl_amount
    safe_total = total or Decimal("1")

    return {
        "brl_amount": brl_amount,
        "brl_percentage": brl_amount / safe_total * Decimal("100"),
        "foreign_amount": foreign_amount,
        "foreign_percentage": foreign_amount / safe_total * Decimal("100"),
        "by_currency": by_currency,
    }


def serialize_concentration(rows: list[ConcentrationRow]) -> list[dict]:
    """Forma JSON-segura (float) de qualquer uma das funcoes `build_*`
    acima -- mesmo raciocinio de `allocation.serialize_allocation_drift`.
    """
    return [
        {
            "key": row["key"],
            "label": row["label"],
            "amount": float(row["amount"]),
            "percentage": float(row["percentage"]),
        }
        for row in rows
    ]


def serialize_currency_exposure(exposure: CurrencyExposure) -> dict:
    return {
        "brl_amount": float(exposure["brl_amount"]),
        "brl_percentage": float(exposure["brl_percentage"]),
        "foreign_amount": float(exposure["foreign_amount"]),
        "foreign_percentage": float(exposure["foreign_percentage"]),
        "by_currency": serialize_concentration(exposure["by_currency"]),
    }
