"""Alocacao de portfolio (Bogleheads-style): alvo x atual x desvio por classe de ativo.

Sem model de alocacao por posicao: a classe de ativo de um `Investment` e
inferida de `kind`/`subtype` (a mesma taxonomia da Pluggy que `tasks.py` usa
para separar previdencia) com uma tag do usuario (`FinanceTag`) tendo
precedencia quando o dado da Pluggy e ambiguo.
"""

from decimal import Decimal
from typing import TypedDict

from .consolidation import latest_positions_by_investment
from .models import (
    Account,
    AssetClass,
    FinanceTag,
    FinanceTagKind,
    Investment,
    PensionPlan,
    PortfolioTarget,
)

# Pluggy `kind` (`FIXED_INCOME | SECURITY | MUTUAL_FUND | EQUITY | ETF | COE`,
# ver tasks.py:PENSION_INVESTMENT_TYPE) mapeado para uma classe de ativo do
# construtor de portfolio. `MUTUAL_FUND`/`ETF`/`COE` sao ambiguos por natureza
# -- um multimercado e um ETF internacional podem chegar com o mesmo `kind` --
# entao caem em `EQUITY_BR` como default conservador e dependem de uma
# `FinanceTag` do usuario para sair dali. `SECURITY` (previdencia) nunca chega
# aqui: `tasks.py` exclui investimentos de previdencia da tabela `Investment`.
KIND_TO_ASSET_CLASS: dict[str, str] = {
    "FIXED_INCOME": AssetClass.FIXED_INCOME,
    "EQUITY": AssetClass.EQUITY_BR,
}

AMBIGUOUS_KINDS = frozenset({"MUTUAL_FUND", "ETF", "COE"})


class AllocationAmount(TypedDict):
    asset_class: str
    amount: Decimal


class DriftRow(TypedDict):
    asset_class: str
    label: str
    target_percentage: Decimal
    actual_percentage: Decimal
    actual_amount: Decimal
    drift_pp: Decimal


def classify_investment_asset_class(investment: Investment, tag: FinanceTag | None) -> str:
    """Classe de ativo de um investimento: tag do usuario > `kind` da Pluggy.

    `tag` e resolvido pelo chamador (um dict pre-carregado, tipicamente) para
    `build_actual_allocation` nao rodar uma query de `FinanceTag` por
    investimento.
    """
    if tag is not None:
        return tag.value
    return KIND_TO_ASSET_CLASS.get(investment.kind.upper(), AssetClass.EQUITY_BR)


def _asset_class_tags(user, kind: str) -> dict[int, FinanceTag]:
    """Tags de `kind` do usuario, indexadas pelo alvo (account_id ou investment_id).

    Uma unica query para todas as tags do dominio -- `build_actual_allocation`
    nao pode custar uma query por investimento/conta.
    """
    by_target: dict[int, FinanceTag] = {}
    for tag in FinanceTag.objects.filter(user=user, kind=kind):
        target_id = tag.account_id or tag.investment_id or tag.goal_id
        if target_id is not None:
            by_target[target_id] = tag
    return by_target


def build_actual_allocation(user) -> list[AllocationAmount]:
    """Alocacao atual por classe de ativo, a partir de dados sincronizados/tagueados.

    - Investimentos: valor de mercado da posicao mais recente
      (`latest_positions_by_investment`), classificados por
      `classify_investment_asset_class`.
    - Previdencia (`PensionPlan.balance`): sempre `AssetClass.PENSION` -- e o
      unico dominio sem ambiguidade nenhuma.
    - Contas: só entram como `CASH_RESERVE` quando explicitamente tagueadas.
      Saldo de conta corrente não-tagueada é dinheiro de gasto, não alocação de
      portfólio -- contar todo saldo de conta como "reserva" infla essa classe
      para qualquer usuário com salário ainda não gasto no mês.
    """
    tags_by_investment = _asset_class_tags(user, FinanceTagKind.ASSET_CLASS)
    totals: dict[str, Decimal] = {}

    positions = latest_positions_by_investment(user)
    investments = Investment.objects.filter(connection__user=user)
    for investment in investments:
        position = positions.get(investment.pk)
        if position is None:
            continue
        asset_class = classify_investment_asset_class(
            investment, tags_by_investment.get(investment.pk)
        )
        totals[asset_class] = totals.get(asset_class, Decimal("0")) + position.market_value

    pension_total = sum(
        (plan.balance for plan in PensionPlan.objects.filter(user=user)), Decimal("0")
    )
    if pension_total:
        totals[AssetClass.PENSION] = totals.get(AssetClass.PENSION, Decimal("0")) + pension_total

    tagged_cash_accounts = FinanceTag.objects.filter(
        user=user, kind=FinanceTagKind.ASSET_CLASS, account__isnull=False
    ).select_related("account")
    for tag in tagged_cash_accounts:
        totals[tag.value] = totals.get(tag.value, Decimal("0")) + tag.account.available_balance

    return [
        {"asset_class": asset_class, "amount": amount}
        for asset_class, amount in totals.items()
        if amount != 0
    ]


def build_allocation_drift(user) -> list[DriftRow]:
    """Junta `PortfolioTarget` (alvo) com `build_actual_allocation` (atual).

    Classe sem alvo definido pelo usuario ainda aparece (alvo 0%) se tiver
    saldo real -- omitir esconderia dinheiro que existe e precisa de decisao.
    """
    targets = {
        target.asset_class: target.target_percentage
        for target in PortfolioTarget.objects.filter(user=user)
    }
    actual = build_actual_allocation(user)
    total_actual = sum((row["amount"] for row in actual), Decimal("0"))

    actual_by_class = {row["asset_class"]: row["amount"] for row in actual}
    all_classes = set(targets) | set(actual_by_class)

    rows: list[DriftRow] = []
    for asset_class in all_classes:
        target_pct = targets.get(asset_class, Decimal("0"))
        amount = actual_by_class.get(asset_class, Decimal("0"))
        actual_pct = (amount / total_actual * Decimal("100")) if total_actual > 0 else Decimal("0")
        is_known_class = asset_class in AssetClass.values
        rows.append(
            {
                "asset_class": asset_class,
                "label": AssetClass(asset_class).label if is_known_class else asset_class,
                "target_percentage": target_pct,
                "actual_percentage": actual_pct,
                "actual_amount": amount,
                "drift_pp": actual_pct - target_pct,
            }
        )
    rows.sort(key=lambda row: -row["target_percentage"])
    return rows


def serialize_allocation_drift(rows: list[DriftRow]) -> list[dict]:
    """Forma JSON-segura (float) de `build_allocation_drift`.

    Mesmo raciocinio de `projections.serialize_future_projection`: um unico
    lugar convertendo Decimal para o que a fronteira (JSON/GraphQL Float)
    aceita, reaproveitado pela persistencia (`PortfolioBuilderReport.drift`),
    pela view de IA e pelo resolver GraphQL.
    """
    return [
        {
            "asset_class": row["asset_class"],
            "label": row["label"],
            "target_percentage": float(row["target_percentage"]),
            "actual_percentage": float(row["actual_percentage"]),
            "actual_amount": float(row["actual_amount"]),
            "drift_pp": float(row["drift_pp"]),
        }
        for row in rows
    ]


def untagged_investments(user) -> list[Investment]:
    """Investimentos cujo `kind` cai numa classe ambigua e ainda nao tem tag.

    A tela do construtor de portfolio usa isto para pedir ao usuario que
    classifique manualmente o que `classify_investment_asset_class` nao
    resolveria com confianca sozinho.
    """
    tagged_ids = set(
        FinanceTag.objects.filter(
            user=user, kind=FinanceTagKind.ASSET_CLASS, investment__isnull=False
        ).values_list("investment_id", flat=True)
    )
    return [
        investment
        for investment in Investment.objects.filter(connection__user=user)
        if investment.kind.upper() in AMBIGUOUS_KINDS and investment.pk not in tagged_ids
    ]


def taggable_cash_accounts(user) -> list[Account]:
    """Contas correntes/poupança que o usuário pode marcar como reserva de emergência.

    Só faz sentido oferecer contas de caixa (checking/savings) -- conta de
    investimento (brokerage) e cartão já entram por outro caminho.
    """
    from .models import AccountType

    return list(
        Account.objects.filter(
            connection__user=user, type__in=(AccountType.CHECKING, AccountType.SAVINGS)
        )
    )
