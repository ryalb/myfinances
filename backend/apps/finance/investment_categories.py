"""Categoria de exibicao de um investimento, para a tela de investimentos.

Taxonomia diferente de `AssetClass`/`allocation.py`: aquela existe para as
metas de alocacao do Portfolio Builder (5 baldes largos, sem FII por decisao
de produto). Esta e so para a listagem/tabela ficar legivel, com FII separado
de Acoes.

A Pluggy nao tem `type: "FII"` (o enum real e FIXED_INCOME | SECURITY |
MUTUAL_FUND | EQUITY | ETF | COE -- ver allocation.py). Um FII chega como
EQUITY ou MUTUAL_FUND com um ticker em `code`. Detectamos pelo padrao de
ticker da B3 (4 letras + "11"), que tambem e usado por alguns "units" de banco
(ex: SANB11, BPAC11) -- por isso o resultado carrega `estimated=True` quando
vem desse heuristico, para a tela avisar que pode estar errado.
"""

import re
from dataclasses import dataclass

from .models import Investment

_FII_TICKER_RE = re.compile(r"^[A-Z]{4}11$")

_LABELS = {
    "fixed_income": "Renda Fixa",
    "fii": "Fundos Imobiliários",
    "equity_intl": "Ações Internacionais",
    "equity_br": "Ações",
    "mutual_fund": "Fundos",
    "etf": "ETF",
    "coe": "COE",
    "other": "Outros",
}


@dataclass(frozen=True)
class DisplayCategory:
    key: str
    label: str
    estimated: bool = False


def _looks_like_fii(code: str) -> bool:
    return bool(_FII_TICKER_RE.match(code.strip().upper()))


def classify_display_category(investment: Investment) -> DisplayCategory:
    kind = (investment.kind or "").strip().upper()
    code = investment.code or ""

    if kind == "FIXED_INCOME":
        return DisplayCategory("fixed_income", _LABELS["fixed_income"])

    if kind in ("EQUITY", "MUTUAL_FUND") and code and _looks_like_fii(str(code)):
        return DisplayCategory("fii", _LABELS["fii"], estimated=True)

    if kind == "EQUITY":
        if investment.currency and investment.currency.upper() != "BRL":
            return DisplayCategory("equity_intl", _LABELS["equity_intl"])
        return DisplayCategory("equity_br", _LABELS["equity_br"])

    if kind == "MUTUAL_FUND":
        return DisplayCategory("mutual_fund", _LABELS["mutual_fund"])

    if kind == "ETF":
        return DisplayCategory("etf", _LABELS["etf"])

    if kind == "COE":
        return DisplayCategory("coe", _LABELS["coe"])

    return DisplayCategory("other", _LABELS["other"])
