"""Categoria de exibicao (Renda Fixa/Acoes/FII/...) para a tela de investimentos.

Table-driven pelo mesmo motivo de test_allocation.py: a taxonomia da Pluggy
(`kind`) e o heuristico de ticker de FII sao a fonte de ambiguidade central
deste modulo.
"""

import pytest

from apps.finance.investment_categories import classify_display_category
from apps.finance.models import Investment


@pytest.mark.parametrize(
    "kind,code,currency,expected_key,expected_estimated",
    [
        ("FIXED_INCOME", "", "BRL", "fixed_income", False),
        ("fixed_income", "", "BRL", "fixed_income", False),
        ("EQUITY", "PETR4", "BRL", "equity_br", False),
        ("EQUITY", "AAPL", "USD", "equity_intl", False),
        ("EQUITY", "KNRI11", "BRL", "fii", True),
        ("MUTUAL_FUND", "HGLG11", "BRL", "fii", True),
        ("MUTUAL_FUND", "", "BRL", "mutual_fund", False),
        ("ETF", "BOVA11", "BRL", "etf", False),
        ("COE", "", "BRL", "coe", False),
        ("OTHER", "", "BRL", "other", False),
        ("", "", "BRL", "other", False),
    ],
)
def test_classify_display_category(kind, code, currency, expected_key, expected_estimated):
    investment = Investment(kind=kind, code=code, currency=currency)

    result = classify_display_category(investment)

    assert result.key == expected_key
    assert result.estimated is expected_estimated


def test_fii_heuristic_false_positive_on_bank_unit_is_a_known_limitation():
    """Units de banco (ex: SANB11, BPAC11) tambem terminam em 11 -- o
    heuristico nao distingue de um FII real. Documentado, nao corrigido aqui.
    """
    unit_share = Investment(kind="EQUITY", code="SANB11", currency="BRL")

    result = classify_display_category(unit_share)

    assert result.key == "fii"
    assert result.estimated is True


def test_etf_is_not_reclassified_as_fii_even_with_matching_ticker():
    investment = Investment(kind="ETF", code="IVVB11", currency="BRL")

    result = classify_display_category(investment)

    assert result.key == "etf"
