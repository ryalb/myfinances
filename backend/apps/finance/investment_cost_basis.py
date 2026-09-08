"""Custo medio de aquisicao de um investimento, a partir do historico bruto de
transacoes da Pluggy (`InvestmentTransaction`).

Usado como fallback de `InvestmentPosition.amount_original`/`amount_profit`
quando a Pluggy nao manda esses campos no payload de investimentos -- visto em
Acoes/FIIs negociados em bolsa, que a Pluggy so expoe custo via o endpoint de
transacoes (`GET /investments/{id}/transactions`), nao no payload da posicao.

Mesmo metodo de custo medio usado pela B3/Receita Federal para apuracao de IR
em renda variavel: cada venda reduz o custo total na mesma proporcao da
quantidade vendida sobre a quantidade total, preservando o preco medio das
cotas restantes.
"""

from collections.abc import Iterable
from decimal import Decimal

from .models import InvestmentTransaction, InvestmentTransactionType


def compute_average_cost_basis(transactions: Iterable[InvestmentTransaction]) -> Decimal | None:
    """`transactions` deve vir ordenada por data (`InvestmentTransaction.Meta.ordering`
    ja garante isso quando passado o `related_manager`, ex. `investment.transactions.all()`)."""
    quantity = Decimal(0)
    cost = Decimal(0)

    for txn in transactions:
        if txn.type == InvestmentTransactionType.BUY and txn.quantity and txn.amount:
            quantity += txn.quantity
            cost += txn.amount
        elif txn.type == InvestmentTransactionType.SELL and txn.quantity and quantity > 0:
            sold_ratio = min(txn.quantity / quantity, Decimal(1))
            cost -= cost * sold_ratio
            quantity -= txn.quantity

    if quantity <= 0 or cost <= 0:
        return None
    return cost
