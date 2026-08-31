"""Alocacao de portfolio (Bogleheads-style): alvo x atual x desvio por classe de ativo.

Sem model de alocacao por posicao: a classe de ativo de um `Investment` e
inferida de `kind`/`subtype` (a mesma taxonomia da Pluggy que `tasks.py` usa
para separar previdencia) com uma tag do usuario (`FinanceTag`) tendo
precedencia quando o dado da Pluggy e ambiguo.
"""

from decimal import ROUND_HALF_UP, Decimal
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


class ContributionRow(TypedDict):
    asset_class: str
    label: str
    target_percentage: Decimal
    actual_percentage: Decimal
    actual_amount: Decimal
    suggested_amount: Decimal


def build_contribution_plan(user, amount: Decimal) -> list[ContributionRow]:
    """Distribui um aporte novo entre as classes de `build_allocation_drift`
    para reduzir o desvio ("rebalancear com dinheiro novo", Bogleheads), em vez
    de sugerir venda de posicoes existentes.

    Por classe, `needed` e o quanto falta para ela chegar ao alvo considerando
    o total *depois* do aporte (`target% * (total_atual + amount)`). Se a soma
    de `needed` cabe no aporte, cada classe subalocada recebe exatamente seu
    `needed` e o restante e rateado por `target_percentage` (todas as classes
    ja no alvo ou acima -- o resto so tem para onde ir pelo peso do alvo). Se
    nao cabe, o aporte inteiro e rateado proporcionalmente ao `needed` de cada
    classe -- nenhuma cobre 100% do proprio deficit.

    Contrato: nunca lanca excecao. `drift` vazio ou `amount <= 0` retornam
    `[]` -- a chamada so faz sentido com pelo menos uma classe e algum valor a
    aportar.
    """
    drift = build_allocation_drift(user)
    if not drift or amount <= 0:
        return []

    total_actual = sum((row["actual_amount"] for row in drift), Decimal("0"))
    needed_by_class = {
        row["asset_class"]: max(
            Decimal("0"),
            row["target_percentage"] / Decimal("100") * (total_actual + amount)
            - row["actual_amount"],
        )
        for row in drift
    }
    total_needed = sum(needed_by_class.values(), Decimal("0"))

    allocated: dict[str, Decimal] = {}
    if total_needed <= amount:
        remainder = amount - total_needed
        total_target_pct = sum((row["target_percentage"] for row in drift), Decimal("0"))
        for row in drift:
            asset_class = row["asset_class"]
            if total_target_pct > 0:
                extra = remainder * row["target_percentage"] / total_target_pct
            else:
                # Nenhum alvo definido (ou todos 0%): sem peso para ratear por
                # alvo, divide igualmente em vez de dividir por zero. A view
                # pede para o usuario definir alvos antes de chegar aqui, mas
                # esta funcao nao deve lancar de qualquer forma.
                extra = remainder / Decimal(len(drift))
            allocated[asset_class] = needed_by_class[asset_class] + extra
    else:
        # total_needed > amount >= 0 implica total_needed > 0: denominador
        # nunca e zero neste ramo.
        for row in drift:
            asset_class = row["asset_class"]
            allocated[asset_class] = amount * needed_by_class[asset_class] / total_needed

    rounded = {
        asset_class: value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for asset_class, value in allocated.items()
    }
    # O arredondamento por linha pode nao somar exatamente `amount` -- ajusta a
    # maior linha pelo residuo para a soma das sugestoes bater com o valor que
    # o usuario efetivamente vai aportar.
    target_total = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    residual = target_total - sum(rounded.values(), Decimal("0"))
    if residual != 0:
        largest_class = max(rounded, key=lambda key: rounded[key])
        rounded[largest_class] += residual

    return [
        {
            "asset_class": row["asset_class"],
            "label": row["label"],
            "target_percentage": row["target_percentage"],
            "actual_percentage": row["actual_percentage"],
            "actual_amount": row["actual_amount"],
            "suggested_amount": rounded[row["asset_class"]],
        }
        for row in drift
    ]


def serialize_contribution_plan(rows: list[ContributionRow]) -> list[dict]:
    """Forma JSON-segura (float) de `build_contribution_plan`.

    Mesmo raciocinio de `serialize_allocation_drift`.
    """
    return [
        {
            "asset_class": row["asset_class"],
            "label": row["label"],
            "target_percentage": float(row["target_percentage"]),
            "actual_percentage": float(row["actual_percentage"]),
            "actual_amount": float(row["actual_amount"]),
            "suggested_amount": float(row["suggested_amount"]),
        }
        for row in rows
    ]


class ReclassifiableInvestment(TypedDict):
    id: int
    name: str
    kind: str
    asset_class: str
    tag_id: int | None


def reclassifiable_investments(user) -> list[ReclassifiableInvestment]:
    """Todos os investimentos do usuario com a classe efetiva atual (tag >
    `kind` inferido) e o id da tag, se houver.

    A tela do construtor de portfolio usa isto para deixar qualquer
    investimento ser reclassificado manualmente -- nao so os de `kind`
    ambiguo -- porque uma aplicacao com `kind` nao-ambiguo (ex: renda fixa)
    pode mesmo assim ser a reserva de emergencia do usuario. `tag_id` presente
    permite a tela oferecer "remover classificacao" e voltar ao default
    inferido.
    """
    tags_by_investment_id = {
        tag.investment_id: tag
        for tag in FinanceTag.objects.filter(
            user=user, kind=FinanceTagKind.ASSET_CLASS, investment__isnull=False
        )
    }
    result: list[ReclassifiableInvestment] = []
    for investment in Investment.objects.filter(connection__user=user).order_by("name"):
        tag = tags_by_investment_id.get(investment.pk)
        result.append(
            {
                "id": investment.id,
                "name": investment.name,
                "kind": investment.kind,
                "asset_class": classify_investment_asset_class(investment, tag),
                "tag_id": tag.id if tag is not None else None,
            }
        )
    return result


class TaggableAccount(TypedDict):
    id: int
    name: str
    type: str
    tag_id: int | None


def taggable_cash_accounts(user) -> list[TaggableAccount]:
    """Contas correntes/poupança do usuário, com o id da tag de reserva de
    emergência se houver.

    Só faz sentido oferecer contas de caixa (checking/savings) -- conta de
    investimento (brokerage) e cartão já entram por outro caminho. `tag_id`
    presente permite a tela oferecer "desmarcar" em vez de só "marcar" --
    sem isto a conta ficava marcada para sempre, sem controle na UI para
    reverter.
    """
    from .models import AccountType

    tag_by_account_id = {
        tag.account_id: tag.id
        for tag in FinanceTag.objects.filter(
            user=user,
            kind=FinanceTagKind.ASSET_CLASS,
            account__isnull=False,
            value=AssetClass.CASH_RESERVE,
        )
    }
    return [
        {
            "id": account.id,
            "name": account.name,
            "type": account.type,
            "tag_id": tag_by_account_id.get(account.id),
        }
        for account in Account.objects.filter(
            connection__user=user, type__in=(AccountType.CHECKING, AccountType.SAVINGS)
        )
    ]
