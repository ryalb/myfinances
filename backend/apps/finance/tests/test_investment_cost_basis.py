"""Custo medio estimado a partir do historico de transacoes -- fallback de
`InvestmentPosition.amount_original` quando a Pluggy nao manda esse campo.

Instancias de `InvestmentTransaction` aqui nunca sao salvas: a funcao so le os
atributos (`type`/`quantity`/`amount`), entao o teste nao precisa de banco --
mesmo raciocinio de `test_investment_categories.py`.
"""

from decimal import Decimal

from apps.finance.investment_cost_basis import compute_average_cost_basis
from apps.finance.models import InvestmentTransaction, InvestmentTransactionType


def _txn(type_, quantity, amount):
    return InvestmentTransaction(type=type_, quantity=Decimal(quantity), amount=Decimal(amount))


def test_no_transactions_returns_none():
    assert compute_average_cost_basis([]) is None


def test_single_buy_is_the_full_cost():
    transactions = [_txn(InvestmentTransactionType.BUY, "30", "3000.00")]

    assert compute_average_cost_basis(transactions) == Decimal("3000.00")


def test_two_buys_sum_the_cost():
    transactions = [
        _txn(InvestmentTransactionType.BUY, "10", "1000.00"),
        _txn(InvestmentTransactionType.BUY, "10", "1200.00"),
    ]

    assert compute_average_cost_basis(transactions) == Decimal("2200.00")


def test_partial_sell_reduces_cost_by_the_same_proportion_as_quantity():
    # Compra 20 cotas por 2000 (custo medio 100/cota), vende metade (10) --
    # sobra metade da quantidade e metade do custo, preservando o preco medio.
    transactions = [
        _txn(InvestmentTransactionType.BUY, "20", "2000.00"),
        _txn(InvestmentTransactionType.SELL, "10", "1500.00"),
    ]

    assert compute_average_cost_basis(transactions) == Decimal("1000.00")


def test_selling_everything_leaves_no_cost_basis():
    transactions = [
        _txn(InvestmentTransactionType.BUY, "20", "2000.00"),
        _txn(InvestmentTransactionType.SELL, "20", "2500.00"),
    ]

    assert compute_average_cost_basis(transactions) is None


def test_non_trade_transactions_without_quantity_are_ignored():
    transactions = [
        _txn(InvestmentTransactionType.BUY, "10", "1000.00"),
        InvestmentTransaction(
            type=InvestmentTransactionType.TAX, quantity=None, amount=Decimal("15.00")
        ),
    ]

    assert compute_average_cost_basis(transactions) == Decimal("1000.00")
