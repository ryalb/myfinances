import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

import requests
from django.db import transaction as db_transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from .consolidation import (
    build_subscription_overview,
    build_user_financial_summary,
    latest_positions_by_investment,
)
from .models import (
    EMBEDDING_DIMENSIONS,
    Account,
    Card,
    CategorizationRule,
    ChatMessageRole,
    Connection,
    DocumentChunk,
    DocumentChunkStatus,
    Embedding,
    FinancialGoal,
    Identity,
    Investment,
    InvestmentPosition,
    PensionPlan,
    SyncJob,
    Transaction,
    TransactionType,
)

logger = logging.getLogger(__name__)

# Ancora do relatorio: sempre entra no contexto, independente de similaridade.
SUMMARY_SOURCE_TYPE = "financial_summary"

TRANSACTION_MONTHS = 6

# Quantas mensagens anteriores entram no prompt como memoria da conversa. Maior
# que isso e o prompt cresce sem necessidade -- a maioria das perguntas de
# acompanhamento se refere so aos ultimos turnos.
CHAT_HISTORY_LIMIT = 12


class AIServiceUnavailable(RuntimeError):
    """Ollama fora do ar, modelo ausente ou destino de inferencia nao permitido.

    Existe para o endpoint responder 503 com texto acionavel em vez de 500 com
    stack trace -- rodando local, "esqueci de subir o Ollama" e o caso comum.
    """


REPORT_DISCLAIMER = (
    "Análise gerada automaticamente a partir dos seus próprios dados, por um modelo "
    "de linguagem rodando localmente. Não é recomendação de investimento nem "
    "consultoria financeira: confira os números na fonte antes de decidir."
)

# O contrato com a UI. Chave fora desta lista nao viaja: a tela nao saberia
# renderizar, e deixar passar convida a LLM a inventar estrutura.
REPORT_TEXT_FIELDS = ("summary", "projections")
REPORT_LIST_FIELDS = ("strengths", "weaknesses", "adjustments", "suggestions")

# Mesmo contrato, para a narracao do simulador de futuro financeiro -- os numeros
# em si vem de `projections.build_future_projection`, a LLM so explica.
PROJECTION_TEXT_FIELDS = ("narrative",)
PROJECTION_LIST_FIELDS = ("leverage_explanation", "goal_commentary")

# Mesmo contrato, para a orientacao Bogleheads do construtor de portfolio -- os
# numeros vem de `allocation.build_allocation_drift`, a LLM so recomenda.
GUIDANCE_TEXT_FIELDS = ("guidance",)
GUIDANCE_LIST_FIELDS = ("rebalancing_actions", "common_mistakes")

# Mesmo contrato, para a sintese do relatorio executivo -- os numeros vem de
# `allocation.build_allocation_drift`/`build_contribution_plan` e
# `projections.build_future_projection`, a LLM so avalia e narra.
EXECUTIVE_TEXT_FIELDS = ("summary",)
EXECUTIVE_LIST_FIELDS = ("goal_fit", "performance_verdict", "contribution_rationale")

# Hosts considerados locais. `ollama` e o nome do servico no docker-compose.
LOCAL_INFERENCE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "ollama"})


def assert_local_inference(url: str) -> None:
    """Recusa mandar o contexto financeiro para fora da maquina.

    O contexto carrega saldo, transacoes, instituicoes e metas. O plano promete
    "100% offline/local sem envio de dados para APIs externas", e ate aqui nada
    garantia isso: um `OLLAMA_URL` remoto exportaria tudo em silencio.
    """
    if os.getenv("AI_ALLOW_REMOTE_INFERENCE", "").lower() == "true":
        return

    host = urlparse(url).hostname
    if host in LOCAL_INFERENCE_HOSTS:
        return

    raise AIServiceUnavailable(
        f"A inferencia esta apontada para '{host}', que nao e local. O contexto "
        f"enviado inclui saldos, transacoes e instituicoes. Suba o Ollama local ou "
        f"defina AI_ALLOW_REMOTE_INFERENCE=true se o envio for intencional."
    )


def _is_numeric_noise(text: str) -> bool:
    """Numero cru ou codigo de moeda: ruido quando ha texto descritivo ao lado.

    O modelo por vezes devolve `{"texto": "...", "valor": 328137.21, "moeda": "BRL"}`
    onde o contrato pede uma string. Sem este filtro o item achatado virava
    "texto — 328137.21 — BRL", repetindo em numero cru o que a frase ja diz (e,
    quando o campo em si e um dict como esse, virava so os numeros sem frase
    nenhuma).
    """
    if re.fullmatch(r"[A-Z]{3}", text):
        return True
    try:
        float(text)
        return True
    except ValueError:
        return False


def _flatten_dict(value: dict) -> str:
    parts = [_as_text(part) for part in value.values() if _as_text(part)]
    descriptive = [part for part in parts if not _is_numeric_noise(part)]
    return " — ".join(descriptive or parts)


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list | tuple):
        return " ".join(_as_text(item) for item in value if _as_text(item))
    if isinstance(value, dict):
        return _flatten_dict(value)
    return str(value)


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # Modelo costuma devolver um paragrafo (ou varias linhas) onde o contrato
        # pede lista.
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list | tuple):
        return [str(value)]

    items = []
    for item in value:
        # `[{"acao": ..., "motivo": ...}]` acontece. Renderizar como
        # "[object Object]" seria pior que achatar em texto.
        text = _flatten_dict(item) if isinstance(item, dict) else _as_text(item)
        if text:
            items.append(text)
    return items


def normalize_report(raw) -> dict:
    """Forma estavel para a UI, a partir do JSON livre da LLM.

    Sem isto a tela quebra na primeira variacao de formato e o usuario ve um painel
    vazio sem saber por que.
    """
    source = raw if isinstance(raw, dict) else {}
    report: dict[str, object] = {}
    for key in REPORT_TEXT_FIELDS:
        report[key] = _as_text(source.get(key))
    for key in REPORT_LIST_FIELDS:
        report[key] = _as_list(source.get(key))
    # Por ultimo: o disclaimer nao e negociavel pelo modelo.
    report["disclaimer"] = REPORT_DISCLAIMER
    return report


def normalize_projection_narrative(raw) -> dict:
    """Mesma normalizacao de `normalize_report`, para o contrato da narracao do
    simulador de futuro financeiro (chaves e formato diferentes)."""
    source = raw if isinstance(raw, dict) else {}
    narrative: dict[str, object] = {}
    for key in PROJECTION_TEXT_FIELDS:
        narrative[key] = _as_text(source.get(key))
    for key in PROJECTION_LIST_FIELDS:
        narrative[key] = _as_list(source.get(key))
    narrative["disclaimer"] = REPORT_DISCLAIMER
    return narrative


def normalize_portfolio_guidance(raw) -> dict:
    """Mesma normalizacao de `normalize_report`, para o contrato da orientacao
    Bogleheads do construtor de portfolio (chaves e formato diferentes)."""
    source = raw if isinstance(raw, dict) else {}
    guidance: dict[str, object] = {}
    for key in GUIDANCE_TEXT_FIELDS:
        guidance[key] = _as_text(source.get(key))
    for key in GUIDANCE_LIST_FIELDS:
        guidance[key] = _as_list(source.get(key))
    guidance["disclaimer"] = REPORT_DISCLAIMER
    return guidance


def normalize_executive_report(raw) -> dict:
    """Mesma normalizacao de `normalize_report`, para o contrato da sintese do
    relatorio executivo (chaves e formato diferentes)."""
    source = raw if isinstance(raw, dict) else {}
    report: dict[str, object] = {}
    for key in EXECUTIVE_TEXT_FIELDS:
        report[key] = _as_text(source.get(key))
    for key in EXECUTIVE_LIST_FIELDS:
        report[key] = _as_list(source.get(key))
    report["disclaimer"] = REPORT_DISCLAIMER
    return report


@dataclass(frozen=True)
class Document:
    """Um documento indexavel de um dominio financeiro.

    `source_type` + `source_id` identificam o documento e sao a chave do upsert:
    reindexar sobrescreve em vez de acumular.
    """

    source_type: str
    source_id: str
    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def _month_key(value: date) -> str:
    return f"{value.year}-{value.month:02d}"


def _format_amount(value, currency: str = "BRL") -> str:
    """Numero no padrao brasileiro: milhar '.', decimal ',', prefixo 'R$' quando BRL.

    Este texto vai direto pro prompt da LLM. Um modelo pequeno tende a copiar a
    formatacao que ve no contexto; sem isto ele copiava o `str(Decimal)` cru
    (`328137.21`) e "corrigia" por conta propria para o padrao americano
    (`328,137.21`) -- o oposto do que a UI espera.
    """
    try:
        amount = Decimal(str(value))
    except Exception:
        return str(value)
    text = f"{amount:,.2f}".translate(str.maketrans(",.", ".,"))
    return f"R$ {text}" if currency == "BRL" else f"{text} {currency}"


def _investment_performance(first, last, currency: str) -> str:
    """Variacao da cota entre a primeira e a ultima posicao sincronizada.

    Sem duas datas distintas nao ha o que comparar -- caso comum em conexoes
    recem-sincronizadas, onde so existe a posicao de hoje.
    """
    if not first or not last or first.pk == last.pk or not first.unit_price:
        return ""
    change = (last.unit_price - first.unit_price) / first.unit_price * Decimal("100")
    return (
        f", variacao de {change:+.2f}% desde {first.as_of_date} "
        f"(cota {_format_amount(first.unit_price, currency)} -> "
        f"{_format_amount(last.unit_price, currency)})"
    )


def _build_summary_document(user) -> Document:
    summary = build_user_financial_summary(user)
    breakdown = summary["breakdown"]
    lines = [
        "# Resumo patrimonial",
        f"Ativos: {_format_amount(summary['assets'])}",
        f"Passivos: {_format_amount(summary['liabilities'])}",
        f"Patrimonio liquido: {_format_amount(summary['net_worth'])}",
        "",
        "## Composicao",
        f"Caixa: {_format_amount(breakdown['cash'])}",
        f"Investimentos: {_format_amount(breakdown['investments'])}",
        f"Previdencia: {_format_amount(breakdown['pension'])}",
        f"Dividas: {_format_amount(breakdown['debts'])}",
        f"Cartoes de credito: {_format_amount(breakdown['credit_cards'])}",
    ]
    return Document(
        source_type=SUMMARY_SOURCE_TYPE,
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"net_worth": str(summary["net_worth"])},
    )


def _build_accounts_document(user) -> Document | None:
    accounts = list(
        Account.objects.filter(connection__user=user)
        .select_related("connection__institution")
        .order_by("name")
    )
    if not accounts:
        return None
    lines = [f"# Contas ({len(accounts)})"]
    for account in accounts:
        # Cheque especial: so aparece se o banco reporta e se ha algo a dizer --
        # a maioria das contas nunca usa, e "limite 0,00" seria ruido.
        overdraft_bits = []
        if account.overdraft_used:
            overdraft_bits.append(
                f"cheque especial usado {_format_amount(account.overdraft_used, account.currency)}"
            )
        if account.overdraft_limit:
            overdraft_bits.append(
                "limite de cheque especial "
                f"{_format_amount(account.overdraft_limit, account.currency)}"
            )
        overdraft_text = f", {', '.join(overdraft_bits)}" if overdraft_bits else ""
        lines.append(
            f"- {account.name} ({account.type}) em {account.connection.institution.name}: "
            f"saldo {_format_amount(account.balance, account.currency)}, disponivel "
            f"{_format_amount(account.available_balance, account.currency)}{overdraft_text}"
        )
    return Document(
        source_type="accounts",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(accounts)},
    )


def _build_cards_document(user) -> Document | None:
    cards = list(Card.objects.filter(connection__user=user).order_by("name"))
    if not cards:
        return None
    lines = [f"# Cartoes de credito ({len(cards)})"]
    for card in cards:
        # Bandeira/nivel e status so aparecem quando a Pluggy reporta -- muitas
        # instituicoes nao devolvem `creditData` completo.
        extra_bits = []
        if card.brand:
            extra_bits.append(f"{card.brand} {card.level}".strip())
        if card.status and card.status.upper() != "ACTIVE":
            extra_bits.append(f"status {card.status}")
        if card.available_credit_limit is not None:
            extra_bits.append(f"limite disponivel {_format_amount(card.available_credit_limit)}")
        extra_text = f" ({', '.join(extra_bits)})" if extra_bits else ""
        lines.append(
            f"- {card.name}: limite {_format_amount(card.credit_limit)}, "
            f"fatura atual {_format_amount(card.current_balance)}, "
            f"vence dia {card.due_day}, fecha dia {card.close_day}{extra_text}"
        )
    return Document(
        source_type="cards",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(cards)},
    )


def _build_investments_document(user) -> Document | None:
    investments = list(Investment.objects.filter(connection__user=user).order_by("name"))
    if not investments:
        return None

    # A primeira posicao vista por investimento e a mais antiga (para o calculo
    # de variacao de cota abaixo); a mais recente vem de `latest_positions_by_
    # investment`, compartilhada com `allocation.build_actual_allocation`.
    earliest: dict[int, InvestmentPosition] = {}
    for position in InvestmentPosition.objects.filter(
        investment__connection__user=user
    ).order_by("investment_id", "as_of_date"):
        earliest.setdefault(position.investment_id, position)
    latest = latest_positions_by_investment(user)

    lines = [f"# Investimentos ({len(investments)})"]
    totals_by_kind: dict[str, Decimal] = {}
    for investment in investments:
        position = latest.get(investment.pk)
        value = position.market_value if position else Decimal("0")
        totals_by_kind[investment.kind] = totals_by_kind.get(investment.kind, Decimal("0")) + value
        as_of = f" em {position.as_of_date}" if position else " (sem posicao registrada)"
        performance = _investment_performance(
            earliest.get(investment.pk), position, investment.currency
        )

        # Rentabilidade e lucro do dia (campos crus da Pluggy, sem uso na
        # posicao antes desta mudanca). "rentabilidade", nunca "variacao": o
        # segundo termo e reservado para a comparacao entre posicoes acima.
        rate_bits = []
        if position and position.last_month_rate is not None:
            rate_bits.append(f"rentabilidade do mes {position.last_month_rate:+.2f}%")
        if position and position.annual_rate is not None:
            rate_bits.append(f"rentabilidade anual {position.annual_rate:+.2f}%")
        if position and position.amount_profit is not None:
            rate_bits.append(
                f"lucro acumulado {_format_amount(position.amount_profit, investment.currency)}"
            )
        rate_text = f", {', '.join(rate_bits)}" if rate_bits else ""

        # Dados cadastrais do ativo (emissor, vencimento, isencao de IR), uteis
        # mesmo antes de existir qualquer posicao sincronizada.
        asset_bits = []
        if investment.due_date:
            asset_bits.append(f"vencimento em {investment.due_date}")
        if investment.issuer:
            asset_bits.append(f"emissor {investment.issuer}")
        if investment.tax_exempt:
            asset_bits.append("isento de IR")
        asset_text = f", {', '.join(asset_bits)}" if asset_bits else ""

        lines.append(
            f"- {investment.name} ({investment.kind}): "
            f"{_format_amount(value, investment.currency)}{as_of}{performance}"
            f"{rate_text}{asset_text}"
        )

    # Concentracao por tipo de ativo: sinal direto pra LLM apontar falta de
    # diversificacao sem ter que somar os itens de cima na cabeca.
    total_value = sum(totals_by_kind.values())
    if total_value > 0 and len(totals_by_kind) > 1:
        lines.append("")
        lines.append("## Distribuicao por tipo de ativo")
        for kind, total in sorted(totals_by_kind.items(), key=lambda item: -item[1]):
            share = total / total_value * Decimal("100")
            lines.append(f"- {kind}: {_format_amount(total)} ({share:.1f}% da carteira)")

    return Document(
        source_type="investments",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(investments)},
    )


def _build_pension_document(user) -> Document | None:
    plans = list(PensionPlan.objects.filter(user=user).order_by("name"))
    if not plans:
        return None
    lines = [f"# Previdencia privada ({len(plans)})"]
    for plan in plans:
        extra_bits = []
        if plan.annual_rate is not None:
            extra_bits.append(f"rentabilidade anual {plan.annual_rate:+.2f}%")
        if plan.amount_profit is not None:
            extra_bits.append(f"lucro acumulado {_format_amount(plan.amount_profit)}")
        extra_text = f", {', '.join(extra_bits)}" if extra_bits else ""
        lines.append(
            f"- {plan.name} ({plan.provider}): saldo {_format_amount(plan.balance)}{extra_text}"
        )
    return Document(
        source_type="pension_plans",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(plans)},
    )


def _build_identity_document(user) -> Document | None:
    """Perfil declarado ao banco (Pluggy `/identity`), quando ha algo a dizer.

    Uma linha por conexao: cada instituicao pode reportar perfil de investidor
    e renda/patrimonio informados de forma independente, e nao ha garantia de
    que coincidam entre bancos.
    """
    identities = list(
        Identity.objects.filter(connection__user=user).select_related("connection__institution")
    )
    lines = []
    for identity in identities:
        facts = []
        if identity.investor_profile:
            facts.append(f"perfil de investidor {identity.investor_profile.lower()}")
        if identity.occupation_description:
            facts.append(f"ocupacao {identity.occupation_description}")
        if identity.informed_income_amount is not None:
            frequency = (
                f" ({identity.informed_income_frequency.lower()})"
                if identity.informed_income_frequency
                else ""
            )
            facts.append(
                f"renda informada {_format_amount(identity.informed_income_amount)}{frequency}"
            )
        if identity.informed_patrimony_amount is not None:
            facts.append(
                "patrimonio informado ao banco "
                f"{_format_amount(identity.informed_patrimony_amount)}"
            )
        if facts:
            lines.append(f"- {identity.connection.institution.name}: {', '.join(facts)}")

    if not lines:
        return None
    return Document(
        source_type="identity",
        source_id=str(user.pk),
        content="\n".join(["# Perfil declarado ao banco"] + lines),
        metadata={"count": len(lines)},
    )


def _build_goals_document(user) -> Document | None:
    goals = list(FinancialGoal.objects.filter(user=user).order_by("name"))
    if not goals:
        return None
    lines = [f"# Metas financeiras ({len(goals)})"]
    for goal in goals:
        progress = (
            float(goal.current_amount / goal.target_amount * 100) if goal.target_amount else 0.0
        )
        alvo = f", alvo em {goal.target_date}" if goal.target_date else ""
        lines.append(
            f"- {goal.name} [{goal.status}]: {_format_amount(goal.current_amount)} de "
            f"{_format_amount(goal.target_amount)} ({progress:.1f}%){alvo}"
        )
    return Document(
        source_type="goals",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(goals)},
    )


_SCENARIO_LABELS = {"conservative": "Conservador", "base": "Base", "aggressive": "Agressivo"}


def _render_projection_lines(data: dict) -> list[str]:
    """Linhas em pt-BR da simulacao de futuro financeiro.

    Reaproveitada pelo documento indexavel (`_build_future_projection_document`) e
    pelo prompt da narracao (`LLMService.generate_future_projection_narrative`): os
    dois precisam descrever os mesmos numeros, um indexado e o outro direto no
    prompt. `data` e a forma ja serializada (float/isoformat) de
    `projections.build_future_projection`, nunca o dict com Decimal/date cru.
    """
    lines = [
        f"Patrimonio atual: {_format_amount(data['current_net_worth'])}",
        f"Aporte mensal medio (ultimos 3 meses): {_format_amount(data['monthly_contribution'])}",
        "",
        "## Cenarios (patrimonio projetado por horizonte)",
    ]
    for name, series in data["scenarios"].items():
        label = _SCENARIO_LABELS.get(name, name)
        parts = ", ".join(f"{years} anos: {_format_amount(value)}" for years, value in series.items())
        lines.append(f"- {label}: {parts}")

    lines.append("")
    lines.append("## Cenario de estresse (choque de mercado + hiato de renda)")
    parts = ", ".join(f"{years} anos: {_format_amount(value)}" for years, value in data["stress"].items())
    lines.append(f"- {parts}")

    if data["leverage_points"]:
        lines.append("")
        lines.append("## Pontos de alavancagem (impacto em 20 anos)")
        for point in data["leverage_points"]:
            lines.append(f"- {point['label']}: {_format_amount(point['impact'])} de diferenca")

    if data["goals"]:
        lines.append("")
        lines.append("## Viabilidade de metas com data-alvo")
        for goal in data["goals"]:
            status = "no caminho" if goal["on_track"] else "fora do caminho"
            lines.append(
                f"- {goal['name']} (alvo {_format_amount(goal['target_amount'])} em "
                f"{goal['target_date']}): {status}, falta cobrir "
                f"{_format_amount(goal['shortfall'])}"
            )
    return lines


def _build_future_projection_document(user) -> Document | None:
    from .projections import build_future_projection, serialize_future_projection

    data = serialize_future_projection(build_future_projection(user))
    if not data["scenarios"]:
        return None
    lines = ["# Simulacao de futuro financeiro", *_render_projection_lines(data)]
    return Document(
        source_type="future_projection",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"horizons": data["horizons"]},
    )


def _render_allocation_lines(drift: list[dict]) -> list[str]:
    """Linhas em pt-BR do desvio de alocacao, uma por classe de ativo.

    Reaproveitada pelo documento indexavel (`_build_allocation_document`) e pelo
    prompt de orientacao (`LLMService.generate_portfolio_builder_guidance`),
    mesmo motivo de `_render_projection_lines`: os dois descrevem os mesmos
    numeros, um indexado e o outro direto no prompt.
    """
    lines = []
    for row in drift:
        lines.append(
            f"- {row['label']}: alvo {row['target_percentage']:.1f}%, atual "
            f"{row['actual_percentage']:.1f}% ({_format_amount(row['actual_amount'])}), "
            f"desvio {row['drift_pp']:+.1f} p.p."
        )
    return lines


def _build_allocation_document(user) -> Document | None:
    from .allocation import build_allocation_drift

    drift = build_allocation_drift(user)
    if not drift:
        return None
    lines = [
        "# Alocacao de portfolio (alvo x atual)",
        *_render_allocation_lines(drift),
    ]
    return Document(
        source_type="portfolio_allocation",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(drift)},
    )


def _render_contribution_plan_lines(plan: list[dict]) -> list[str]:
    """Linhas em pt-BR do plano de aporte, uma por classe de ativo.

    Mesmo raciocinio de `_render_allocation_lines`/`_render_projection_lines`:
    reaproveitada apenas pelo prompt de `LLMService.generate_executive_report`
    -- o plano de aporte nao tem documento indexavel proprio, so existe no
    momento em que o relatorio executivo e gerado.
    """
    lines = []
    for row in plan:
        lines.append(
            f"- {row['label']}: alvo {row['target_percentage']:.1f}%, atual "
            f"{row['actual_percentage']:.1f}% ({_format_amount(row['actual_amount'])}), "
            f"sugestao de aporte {_format_amount(row['suggested_amount'])}"
        )
    return lines


def _build_subscriptions_document(user) -> Document | None:
    overview = build_subscription_overview(user)
    if not overview["active_count"]:
        return None
    lines = [
        "# Assinaturas e despesas recorrentes",
        f"Total recorrente mensal: {_format_amount(overview['monthly_recurring_total'])} "
        f"em {overview['active_count']} assinaturas ativas",
        f"Pago no mes: {_format_amount(overview['paid_this_month'])}",
        f"Pendente no mes: {_format_amount(overview['pending_this_month'])}",
        f"Atrasado: {_format_amount(overview['overdue_total'])}",
    ]
    if overview["overdue"]:
        lines.append("")
        lines.append("## Atrasados")
        for item in overview["overdue"]:
            lines.append(
                f"- {item['name']}: {_format_amount(item['amount'])} venceu em {item['due_date']}"
            )
    if overview["upcoming"]:
        lines.append("")
        lines.append("## Proximos vencimentos")
        for item in overview["upcoming"]:
            lines.append(
                f"- {item['name']}: {_format_amount(item['amount'])} vence em {item['due_date']}"
            )
    return Document(
        source_type="subscriptions",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"active_count": overview["active_count"]},
    )


def _build_rules_document(user) -> Document | None:
    rules = list(
        CategorizationRule.objects.filter(user=user, is_active=True).order_by(
            "priority", "-created_at"
        )
    )
    if not rules:
        return None
    lines = [f"# Regras de categorizacao ativas ({len(rules)})"]
    for rule in rules:
        lines.append(f"- '{rule.pattern}' -> {rule.category} (prioridade {rule.priority})")
    return Document(
        source_type="categorization_rules",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(rules)},
    )


def _build_sync_history_document(user) -> Document | None:
    connections = list(
        Connection.objects.filter(user=user).select_related("institution").order_by("id")
    )
    if not connections:
        return None
    lines = [f"# Conexoes e sincronizacao ({len(connections)})"]
    for connection in connections:
        lines.append(
            f"- {connection.institution.name}: status {connection.status}, "
            f"ultima sync {connection.last_synced_at}"
        )
        if connection.error_message:
            lines.append(f"  erro: {connection.error_message}")

    recent_jobs = SyncJob.objects.filter(connection__user=user).order_by("-created_at")[:10]
    if recent_jobs:
        lines.append("")
        lines.append("## Ultimos jobs de sincronizacao")
        for job in recent_jobs:
            lines.append(f"- {job.kind} [{job.status}] em {job.created_at:%Y-%m-%d %H:%M}")
    return Document(
        source_type="sync_history",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"connections": len(connections)},
    )


def _build_transaction_documents(user, months: int = TRANSACTION_MONTHS) -> list[Document]:
    """Um documento por mes.

    Meses separados porque a pergunta costuma ser temporal ("gastei mais em que?"):
    um unico documento com todo o historico competiria com os outros dominios como
    um bloco indivisivel e venceria por tamanho, nao por relevancia.

    As somas saem do banco (`TruncMonth` + `Sum`) em vez de acumuladas em Python:
    tres queries fixas, independente de quantos meses ou lancamentos existirem.
    """
    from django.db.models import Count, Q, Sum
    from django.db.models.functions import TruncMonth

    today = timezone.localdate()
    cutoff_year, cutoff_month = today.year, today.month
    for _ in range(months - 1):
        cutoff_month -= 1
        if cutoff_month == 0:
            cutoff_month = 12
            cutoff_year -= 1
    cutoff = date(cutoff_year, cutoff_month, 1)

    owned = Q(account__connection__user=user) | Q(card__connection__user=user)
    base = Transaction.objects.filter(owned, booked_at__date__gte=cutoff)

    totals: dict[str, dict] = {}
    for row in (
        base.annotate(month=TruncMonth("booked_at"))
        .values("month", "type")
        .annotate(total=Sum("amount"), count=Count("id"))
    ):
        bucket = totals.setdefault(
            _month_key(row["month"]),
            {"credits": Decimal("0"), "debits": Decimal("0"), "count": 0, "categories": {}},
        )
        bucket["count"] += row["count"]
        if row["type"] == TransactionType.CREDIT:
            bucket["credits"] = row["total"] or Decimal("0")
        else:
            bucket["debits"] = row["total"] or Decimal("0")

    for row in (
        base.filter(type=TransactionType.DEBIT)
        .annotate(month=TruncMonth("booked_at"))
        .values("month", "category")
        .annotate(total=Sum("amount"))
    ):
        bucket = totals.get(_month_key(row["month"]))
        if bucket is None:
            continue
        label = row["category"] or "sem categoria"
        bucket["categories"][label] = row["total"] or Decimal("0")

    # Os maiores lancamentos precisam das linhas em si. Sem window function,
    # ordena por valor e corta os 15 primeiros de cada mes em memoria.
    largest: dict[str, list[Transaction]] = {}
    for tx in base.order_by("-amount").only(
        "description",
        "amount",
        "currency",
        "type",
        "category",
        "booked_at",
        "merchant_name",
        "installment_number",
        "installment_total",
        "payment_method",
        "payment_payer",
        "payment_receiver",
    ):
        rows = largest.setdefault(_month_key(tx.booked_at.date()), [])
        if len(rows) < 15:
            rows.append(tx)

    documents = []
    for month, bucket in totals.items():
        lines = [
            f"# Transacoes de {month} ({bucket['count']} lancamentos)",
            f"Receitas: {_format_amount(bucket['credits'])}",
            f"Despesas: {_format_amount(bucket['debits'])}",
            "",
            "## Despesas por categoria",
        ]
        for category, total in sorted(bucket["categories"].items(), key=lambda item: -item[1]):
            lines.append(f"- {category}: {_format_amount(total)}")

        lines.append("")
        lines.append("## Maiores lancamentos")
        for tx in largest.get(month, []):
            # Estabelecimento, parcela e contraparte de PIX/TED: campos crus da
            # Pluggy, sem uso nesta linha antes desta mudanca.
            detail_bits = []
            if tx.merchant_name:
                detail_bits.append(f"estabelecimento {tx.merchant_name}")
            if tx.installment_number and tx.installment_total:
                detail_bits.append(f"parcela {tx.installment_number}/{tx.installment_total}")
            if tx.payment_method:
                counterparty = (tx.payment_receiver or {}).get("name") or (
                    tx.payment_payer or {}
                ).get("name")
                detail_bits.append(
                    f"{tx.payment_method} com {counterparty}" if counterparty else tx.payment_method
                )
            detail_text = f", {', '.join(detail_bits)}" if detail_bits else ""
            lines.append(
                f"- {tx.booked_at:%Y-%m-%d} {tx.description}: "
                f"{_format_amount(tx.amount, tx.currency)} "
                f"({tx.type}, {tx.category or 'sem categoria'}){detail_text}"
            )

        documents.append(
            Document(
                source_type="transactions",
                source_id=month,
                content="\n".join(lines),
                metadata={"month": month, "count": bucket["count"]},
            )
        )
    return documents


def build_user_documents(user) -> list[Document]:
    """Documentos por dominio financeiro.

    Dominio sem dado e omitido: um chunk "Cartoes (0)" nao ajuda a responder nada
    e ainda concorre na busca por similaridade.
    """
    documents = [_build_summary_document(user)]
    for builder in (
        _build_accounts_document,
        _build_cards_document,
        _build_investments_document,
        _build_pension_document,
        _build_identity_document,
        _build_goals_document,
        _build_future_projection_document,
        _build_allocation_document,
        _build_subscriptions_document,
        _build_rules_document,
        _build_sync_history_document,
    ):
        document = builder(user)
        if document is not None:
            documents.append(document)
    documents.extend(_build_transaction_documents(user))
    return documents


def _ollama_error_detail(response) -> str:
    """Mensagem de erro do Ollama, que vem em `{"error": "..."}`."""
    try:
        payload = response.json()
    except ValueError:
        return (response.text or "").strip()[:300]
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return (response.text or "").strip()[:300]


def _ollama_post(url: str, payload: dict, *, model: str, timeout: int) -> dict:
    """POST no Ollama com erro acionavel.

    `raise_for_status()` sozinho produz "404 Client Error" e **descarta o corpo** --
    que no Ollama diz exatamente o que fazer. Um modelo nao baixado responde 404 com
    `model "X" not found, try pulling it first`, indistinguivel de endpoint
    inexistente se a mensagem for perdida.
    """
    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise AIServiceUnavailable(f"Nao foi possivel falar com o Ollama em {url}: {exc}") from exc

    if response.status_code >= 400:
        detail = _ollama_error_detail(response)
        hint = ""
        if "not found" in detail.lower():
            hint = (
                f" Rode `ollama pull {model}`"
                f" (ou `docker compose exec ollama ollama pull {model}`)."
            )
        raise AIServiceUnavailable(
            f"Ollama respondeu {response.status_code} para o modelo '{model}': {detail}.{hint}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceUnavailable(
            f"Resposta do Ollama para '{model}' nao e JSON: {(response.text or '')[:200]}"
        ) from exc


def _ollama_stream_lines(url: str, payload: dict, *, model: str, timeout: int):
    """Abre uma chamada em streaming ao Ollama, com o mesmo erro acionavel de
    `_ollama_post`.

    A checagem de status acontece aqui, antes de qualquer byte do corpo ser
    consumido (`requests` ja recebeu os headers nesse ponto, mesmo com
    `stream=True`) -- por isso o chamador pode tratar `AIServiceUnavailable` de
    forma sincrona e responder 503 antes de abrir um `StreamingHttpResponse`
    que falharia no meio, sem chance de trocar o status code.
    """
    try:
        response = requests.post(url, json=payload, timeout=timeout, stream=True)
    except requests.RequestException as exc:
        raise AIServiceUnavailable(f"Nao foi possivel falar com o Ollama em {url}: {exc}") from exc

    if response.status_code >= 400:
        detail = _ollama_error_detail(response)
        hint = ""
        if "not found" in detail.lower():
            hint = (
                f" Rode `ollama pull {model}`"
                f" (ou `docker compose exec ollama ollama pull {model}`)."
            )
        raise AIServiceUnavailable(
            f"Ollama respondeu {response.status_code} para o modelo '{model}': {detail}.{hint}"
        )

    return response.iter_lines(decode_unicode=True)


def _iter_ollama_stream_text(lines):
    """Extrai o texto incremental de um stream ndjson do Ollama
    (`{"response": "...", "done": false}` por linha), parando no `done: true`.
    """
    for line in lines:
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        chunk = payload.get("response", "")
        if chunk:
            yield chunk
        if payload.get("done"):
            break


class RAGService:
    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        assert_local_inference(self.ollama_url)

    def _get_embedding(self, text: str) -> list[float]:
        payload = _ollama_post(
            f"{self.ollama_url}/api/embeddings",
            {"model": self.embedding_model, "prompt": text},
            model=self.embedding_model,
            timeout=60,
        )

        vector = payload.get("embedding") or []
        if len(vector) != EMBEDDING_DIMENSIONS:
            # Sem esta checagem o erro apareceria como falha do Postgres na
            # insercao, sem dizer que o modelo e o problema.
            raise AIServiceUnavailable(
                f"O modelo '{self.embedding_model}' devolveu {len(vector)} dimensoes, "
                f"mas a coluna espera {EMBEDDING_DIMENSIONS}. Troque o modelo ou "
                f"altere EMBEDDING_DIMENSIONS e gere a migration."
            )
        return vector

    def index_user_context(self, user) -> dict:
        """Sincroniza o indice do usuario com os dados atuais.

        Reindexa apenas o documento cujo conteudo mudou (ou que foi embedado por
        outro modelo). Antes disto cada relatorio gerado criava um chunk novo por
        `create()`, acumulando duplicatas e reembedando tudo a cada requisicao.
        """
        documents = build_user_documents(user)
        existing = {
            (chunk.source_type, chunk.source_id): chunk
            for chunk in DocumentChunk.objects.filter(user=user).select_related("embedding")
        }

        indexed = 0
        skipped = 0
        for document in documents:
            chunk = existing.get((document.source_type, document.source_id))
            if self._is_fresh(chunk, document):
                skipped += 1
                continue

            vector = self._get_embedding(document.content)
            with db_transaction.atomic():
                chunk, _ = DocumentChunk.objects.update_or_create(
                    user=user,
                    source_type=document.source_type,
                    source_id=document.source_id,
                    defaults={
                        "content": document.content,
                        "content_hash": document.digest,
                        "metadata": document.metadata,
                        "status": DocumentChunkStatus.INDEXED,
                        "indexed_at": timezone.now(),
                    },
                )
                Embedding.objects.update_or_create(
                    chunk=chunk,
                    defaults={"vector": vector, "model": self.embedding_model},
                )
            indexed += 1

        # Dominio que deixou de existir (usuario removeu todos os cartoes, mes saiu
        # da janela) precisa sair do indice, senao a LLM cita dado que nao existe.
        current_keys = {(doc.source_type, doc.source_id) for doc in documents}
        stale_ids = [chunk.pk for key, chunk in existing.items() if key not in current_keys]
        removed = 0
        if stale_ids:
            removed, _ = DocumentChunk.objects.filter(pk__in=stale_ids).delete()

        logger.info(
            "Indice RAG do usuario %s: %s indexados, %s inalterados, %s removidos",
            user.pk,
            indexed,
            skipped,
            removed,
        )
        return {"indexed": indexed, "skipped": skipped, "removed": removed}

    def _is_fresh(self, chunk, document: Document) -> bool:
        if chunk is None or chunk.status != DocumentChunkStatus.INDEXED:
            return False
        if chunk.content_hash != document.digest:
            return False
        embedding = getattr(chunk, "embedding", None)
        # Modelo diferente produz vetor em outro espaco: comparar com os demais
        # daria similaridade sem sentido.
        return embedding is not None and embedding.model == self.embedding_model

    def search(self, user, query: str, top_k: int = 5, source_types=None) -> list[dict]:
        """Busca por similaridade de cosseno no proprio Postgres.

        Antes a similaridade era calculada em Python varrendo todos os chunks do
        usuario, o que ignorava o pgvector e nao usava indice nenhum.
        """
        query_vector = self._get_embedding(query)
        queryset = Embedding.objects.filter(
            chunk__user=user, chunk__status=DocumentChunkStatus.INDEXED
        )
        if source_types:
            queryset = queryset.filter(chunk__source_type__in=source_types)

        rows = (
            queryset.annotate(distance=CosineDistance("vector", query_vector))
            .order_by("distance")
            .select_related("chunk")[:top_k]
        )
        return [{"chunk": row.chunk, "similarity": 1.0 - float(row.distance)} for row in rows]

    def retrieve_report_context(self, user, query: str, top_k: int = 6) -> list[dict]:
        """Contexto do relatorio de portfolio.

        Resumo patrimonial e investimentos entram sempre: sao a ancora do
        relatorio e perderiam a disputa de similaridade contra um mes de
        transacoes, que tem muito mais texto sobre qualquer assunto especifico.
        Investimentos entra garantido junto porque avaliar performance da
        carteira e sugerir aportes e o pedido mais comum deste relatorio -- sem
        isso a resposta dependia da sorte da busca semantica.
        """
        anchor_types = (SUMMARY_SOURCE_TYPE, "investments")
        context = []
        anchored_types = set()
        for source_type in anchor_types:
            anchor = list(
                Embedding.objects.filter(
                    chunk__user=user,
                    chunk__status=DocumentChunkStatus.INDEXED,
                    chunk__source_type=source_type,
                ).select_related("chunk")[:1]
            )
            if anchor:
                context.append({"chunk": anchor[0].chunk, "similarity": 1.0})
                anchored_types.add(source_type)

        for item in self.search(user, query, top_k=top_k):
            if item["chunk"].source_type not in anchored_types:
                context.append(item)
        return context

    def retrieve_future_projection_context(self, user) -> list[dict]:
        """Contexto para a narracao do simulador de futuro financeiro.

        Sem busca por similaridade: este relatorio nao tem campo de busca livre
        como o de portfolio, so narra numeros ja calculados -- o resumo
        patrimonial, a propria simulacao e as metas bastam como contexto
        qualitativo de apoio.
        """
        anchor_types = (SUMMARY_SOURCE_TYPE, "future_projection", "goals")
        context = []
        for source_type in anchor_types:
            anchor = list(
                Embedding.objects.filter(
                    chunk__user=user,
                    chunk__status=DocumentChunkStatus.INDEXED,
                    chunk__source_type=source_type,
                ).select_related("chunk")[:1]
            )
            if anchor:
                context.append({"chunk": anchor[0].chunk, "similarity": 1.0})
        return context

    def retrieve_portfolio_builder_context(self, user) -> list[dict]:
        """Contexto para a orientacao Bogleheads do construtor de portfolio.

        Mesmo raciocinio de `retrieve_future_projection_context`: sem busca por
        similaridade, so os dominios qualitativos que ajudam a LLM a explicar o
        desvio de alocacao -- a propria alocacao, investimentos (para citar
        concentracao por tipo) e o resumo patrimonial.
        """
        anchor_types = (SUMMARY_SOURCE_TYPE, "portfolio_allocation", "investments")
        context = []
        for source_type in anchor_types:
            anchor = list(
                Embedding.objects.filter(
                    chunk__user=user,
                    chunk__status=DocumentChunkStatus.INDEXED,
                    chunk__source_type=source_type,
                ).select_related("chunk")[:1]
            )
            if anchor:
                context.append({"chunk": anchor[0].chunk, "similarity": 1.0})
        return context

    def retrieve_executive_report_context(self, user) -> list[dict]:
        """Contexto para a sintese do relatorio executivo.

        Uniao dos dominios ancorados pelos tres relatorios que este sintetiza
        (`retrieve_report_context`, `retrieve_future_projection_context`,
        `retrieve_portfolio_builder_context`): resumo patrimonial, investimentos
        (performance/concentracao), metas, simulacao de futuro financeiro e
        alocacao de portfolio. Sem busca por similaridade, mesmo motivo dos
        outros dois relatorios "so narram numeros ja calculados" -- as tres
        perguntas do usuario (a alocacao faz sentido pra meta, o rendimento
        esta bom, quanto aportar) dependem desses cinco dominios sempre, nunca
        de uma pergunta livre.
        """
        anchor_types = (
            SUMMARY_SOURCE_TYPE,
            "investments",
            "goals",
            "future_projection",
            "portfolio_allocation",
        )
        context = []
        for source_type in anchor_types:
            anchor = list(
                Embedding.objects.filter(
                    chunk__user=user,
                    chunk__status=DocumentChunkStatus.INDEXED,
                    chunk__source_type=source_type,
                ).select_related("chunk")[:1]
            )
            if anchor:
                context.append({"chunk": anchor[0].chunk, "similarity": 1.0})
        return context

    def retrieve_chat_context(self, user, query: str, top_k: int = 6) -> list[dict]:
        """Contexto do chat de IA.

        Sem dominio fixo como os outros relatorios: o chat responde sobre
        qualquer coisa indexada (contas, cartoes, investimentos, transacoes,
        assinaturas...), entao so o resumo patrimonial e ancorado -- o resto
        vem inteiramente da busca semantica pela mensagem do usuario.
        """
        context = []
        anchor = list(
            Embedding.objects.filter(
                chunk__user=user,
                chunk__status=DocumentChunkStatus.INDEXED,
                chunk__source_type=SUMMARY_SOURCE_TYPE,
            ).select_related("chunk")[:1]
        )
        if anchor:
            context.append({"chunk": anchor[0].chunk, "similarity": 1.0})

        for item in self.search(user, query, top_k=top_k):
            if item["chunk"].source_type != SUMMARY_SOURCE_TYPE:
                context.append(item)
        return context


class LLMService:
    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.chat_model = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:14b")
        assert_local_inference(self.ollama_url)

    def generate_portfolio_report(self, context_chunks: list[dict]) -> dict:
        context_text = "\n\n".join(
            f"[Fonte: {item['chunk'].source_type}/{item['chunk'].source_id}]\n"
            f"{item['chunk'].content}"
            for item in context_chunks
            if item.get("chunk")
        )

        prompt = (
            "Você é um assistente financeiro especializado em investimentos no Brasil. "
            "Com base nos dados reais do usuário abaixo, gere um relatório estruturado em JSON.\n\n"
            "Regras obrigatórias:\n"
            "- Use apenas os dados fornecidos; não invente valores, instituições, fundos ou tickers.\n"
            "- Formate valores monetários no padrão brasileiro: separador de milhar '.', separador "
            "decimal ',' e prefixo 'R$ ' (ex.: R$ 1.234,56). Nunca use o padrão americano (1,234.56).\n"
            "- Cada item das listas deve ser uma frase única em texto simples (string), nunca um "
            "objeto ou par chave/valor.\n\n"
            f"Contexto:\n{context_text}\n\n"
            "Retorne um JSON com as chaves:\n"
            "- summary: texto corrido (string) com o resumo executivo da saúde financeira\n"
            "- strengths: lista de frases com pontos fortes\n"
            "- weaknesses: lista de frases com pontos de atenção\n"
            "- adjustments: lista de frases avaliando a performance dos fundos e aplicações atuais "
            "(use a variação de cota e a distribuição por tipo de ativo do contexto de investimentos; "
            "compare com referências conhecidas como CDI, IPCA ou Ibovespa quando fizer sentido) e "
            "apontando concentração de risco por tipo de ativo\n"
            "- suggestions: lista de frases sugerindo classes de fundos ou FIIs (ex.: FII de papel, "
            "FII de tijolo, fundo multimercado, renda fixa, Tesouro Direto) que ajudariam a "
            "diversificar a carteira atual, cada uma com uma justificativa curta ligada à lacuna "
            "identificada; não cite nomes de fundos ou tickers específicos, pois você não tem acesso "
            "a dados de mercado atualizados\n"
            "- projections: texto curto (string) com projeções baseadas no comportamento histórico\n"
        )

        payload = _ollama_post(
            f"{self.ollama_url}/api/generate",
            {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            model=self.chat_model,
            timeout=300,
        )

        content = payload.get("response", "{}")
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            # `format=json` nao garante JSON valido; devolver o texto cru e melhor
            # que perder a resposta inteira.
            raw = {"summary": content}

        report = normalize_report(raw)

        # Rastreabilidade: as fontes vem do que foi realmente recuperado, nao do
        # que a LLM diz ter usado.
        report["sources"] = [
            {
                "source_type": item["chunk"].source_type,
                "source_id": item["chunk"].source_id,
                "similarity": round(item["similarity"], 4),
            }
            for item in context_chunks
            if item.get("chunk")
        ]
        return report

    def generate_future_projection_narrative(
        self, context_chunks: list[dict], projection_data: dict
    ) -> dict:
        """Narra em pt-BR uma simulacao ja calculada por `projections.py`.

        `projection_data` e a forma serializada (float/isoformat) do payload --
        os numeros entram no prompt diretamente, nao so via chunk indexado, para a
        narracao nunca depender de o dominio `future_projection` ja ter sido
        (re)indexado a tempo.
        """
        context_text = "\n\n".join(
            f"[Fonte: {item['chunk'].source_type}/{item['chunk'].source_id}]\n"
            f"{item['chunk'].content}"
            for item in context_chunks
            if item.get("chunk")
        )
        projection_text = "\n".join(_render_projection_lines(projection_data))

        prompt = (
            "Você é um planejador financeiro especializado em independência financeira "
            "no Brasil. Os números da simulação abaixo já foram calculados por código "
            "determinístico; sua tarefa é apenas explicá-los em linguagem natural, nunca "
            "recalculá-los ou inventar valores diferentes dos fornecidos.\n\n"
            "Regras obrigatórias:\n"
            "- Use apenas os números da simulação e do contexto abaixo; não invente valores.\n"
            "- Formate valores monetários no padrão brasileiro: separador de milhar '.', "
            "separador decimal ',' e prefixo 'R$ ' (ex.: R$ 1.234,56). Nunca use o padrão "
            "americano (1,234.56).\n"
            "- Cada item das listas deve ser uma frase única em texto simples (string), "
            "nunca um objeto ou par chave/valor.\n\n"
            f"Simulação:\n{projection_text}\n\n"
            f"Contexto adicional:\n{context_text}\n\n"
            "Retorne um JSON com as chaves:\n"
            "- narrative: texto corrido (string) explicando os cenários (conservador, base, "
            "agressivo e o de estresse) e o que eles significam para a vida financeira do "
            "usuário\n"
            "- leverage_explanation: lista de frases explicando por que cada ponto de "
            "alavancagem listado na simulação tem esse impacto no resultado de 20 anos\n"
            "- goal_commentary: lista de frases comentando a viabilidade de cada meta com "
            "data-alvo listada na simulação (lista vazia se não houver nenhuma)\n"
        )

        payload = _ollama_post(
            f"{self.ollama_url}/api/generate",
            {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            model=self.chat_model,
            timeout=300,
        )

        content = payload.get("response", "{}")
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {"narrative": content}

        narrative = normalize_projection_narrative(raw)
        narrative["sources"] = [
            {
                "source_type": item["chunk"].source_type,
                "source_id": item["chunk"].source_id,
                "similarity": round(item["similarity"], 4),
            }
            for item in context_chunks
            if item.get("chunk")
        ]
        return narrative

    def generate_portfolio_builder_guidance(
        self, context_chunks: list[dict], drift: list[dict]
    ) -> dict:
        """Orientacao Bogleheads em pt-BR sobre um desvio de alocacao ja calculado.

        `drift` vem de `allocation.build_allocation_drift` -- os numeros entram no
        prompt diretamente, mesmo raciocinio de `generate_future_projection_narrative`.
        Reaproveita literalmente as regras de "so dados fornecidos" e "classe de
        fundo, nunca ticker" de `generate_portfolio_report`: nenhuma das duas
        narracoes tem acesso a dado de mercado atualizado.
        """
        context_text = "\n\n".join(
            f"[Fonte: {item['chunk'].source_type}/{item['chunk'].source_id}]\n"
            f"{item['chunk'].content}"
            for item in context_chunks
            if item.get("chunk")
        )
        drift_text = "\n".join(_render_allocation_lines(drift))

        prompt = (
            "Você é um consultor de investimentos no estilo Bogleheads (baixo custo, "
            "diversificação ampla, buy-and-hold). Os números de alocação abaixo já "
            "foram calculados por código determinístico; sua tarefa é apenas explicar "
            "o desvio e recomendar ajustes, nunca recalcular os números.\n\n"
            "Regras obrigatórias:\n"
            "- Use apenas os números abaixo e o contexto fornecido; não invente valores.\n"
            "- Formate valores monetários no padrão brasileiro (R$ 1.234,56).\n"
            "- Sugira classes de fundos (ex.: Tesouro Selic, fundo multimercado, ETF de "
            "ações internacionais) para corrigir cada desvio; nunca cite ticker ou nome "
            "de fundo específico, pois você não tem acesso a dados de mercado atualizados.\n"
            "- Cada item das listas deve ser uma frase única em texto simples (string), "
            "nunca um objeto ou par chave/valor.\n\n"
            f"Alocação (alvo x atual):\n{drift_text}\n\n"
            f"Contexto adicional:\n{context_text}\n\n"
            "Retorne um JSON com as chaves:\n"
            "- guidance: texto corrido (string) resumindo o estado da carteira frente ao "
            "alvo definido pelo usuário\n"
            "- rebalancing_actions: lista de frases com ações concretas de rebalanceamento "
            "(o que priorizar no próximo aporte, ou o que reduzir) para cada classe fora do "
            "alvo\n"
            "- common_mistakes: lista de frases apontando erros comuns de diversificação "
            "identificáveis nos dados fornecidos (concentração, falta de classe, etc.)\n"
        )

        payload = _ollama_post(
            f"{self.ollama_url}/api/generate",
            {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            model=self.chat_model,
            timeout=300,
        )

        content = payload.get("response", "{}")
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {"guidance": content}

        guidance = normalize_portfolio_guidance(raw)
        guidance["sources"] = [
            {
                "source_type": item["chunk"].source_type,
                "source_id": item["chunk"].source_id,
                "similarity": round(item["similarity"], 4),
            }
            for item in context_chunks
            if item.get("chunk")
        ]
        return guidance

    def generate_executive_report(
        self,
        context_chunks: list[dict],
        drift: list[dict],
        projection: dict,
        contribution_plan: list[dict],
    ) -> dict:
        """Sintese em pt-BR das tres perguntas do relatorio executivo: a alocacao
        atual faz sentido para as metas, o rendimento esta bom ou vale mudar de
        aplicacao, e quanto aportar em cada classe no proximo aporte.

        `drift` (`allocation.build_allocation_drift`), `projection`
        (`projections.serialize_future_projection`) e `contribution_plan`
        (`allocation.build_contribution_plan`) ja foram calculados por codigo
        deterministico; a LLM so avalia e narra, nunca recalcula -- mesmo
        raciocinio de `generate_future_projection_narrative` e
        `generate_portfolio_builder_guidance`, que este metodo sintetiza.
        """
        context_text = "\n\n".join(
            f"[Fonte: {item['chunk'].source_type}/{item['chunk'].source_id}]\n"
            f"{item['chunk'].content}"
            for item in context_chunks
            if item.get("chunk")
        )
        drift_text = "\n".join(_render_allocation_lines(drift))
        projection_text = "\n".join(_render_projection_lines(projection))
        plan_text = "\n".join(_render_contribution_plan_lines(contribution_plan))

        prompt = (
            "Você é um consultor financeiro que responde de forma direta e objetiva "
            "três perguntas do usuário sobre a própria carteira, no estilo Bogleheads "
            "(baixo custo, diversificação ampla, buy-and-hold). Todos os números abaixo "
            "já foram calculados por código determinístico; sua tarefa é apenas avaliar "
            "e explicar, nunca recalcular ou inventar valores diferentes dos fornecidos.\n\n"
            "Regras obrigatórias:\n"
            "- Use apenas os números e o contexto abaixo; não invente valores, "
            "instituições, fundos ou tickers.\n"
            "- Formate valores monetários no padrão brasileiro: separador de milhar '.', "
            "separador decimal ',' e prefixo 'R$ ' (ex.: R$ 1.234,56). Nunca use o padrão "
            "americano (1,234.56).\n"
            "- Nunca cite ticker ou nome de fundo específico, pois você não tem acesso a "
            "dados de mercado atualizados; fale em classes de ativo (ex.: renda fixa, "
            "Tesouro Direto, fundo multimercado, ações internacionais).\n"
            "- Cada item das listas deve ser uma frase única em texto simples (string), "
            "nunca um objeto ou par chave/valor.\n\n"
            f"Alocação (alvo x atual):\n{drift_text}\n\n"
            f"Simulação de futuro financeiro e viabilidade de metas:\n{projection_text}\n\n"
            f"Plano de aporte sugerido para o próximo aporte:\n{plan_text}\n\n"
            f"Contexto adicional:\n{context_text}\n\n"
            "Retorne um JSON com as chaves:\n"
            "- summary: texto corrido (string) respondendo de forma direta se a carteira "
            "atual faz sentido para os objetivos do usuário\n"
            "- goal_fit: lista de frases avaliando, para cada meta com data-alvo listada "
            "na simulação, se a alocação atual ajuda a alcançá-la (cruze a viabilidade da "
            "meta com a alocação e a concentração por tipo de ativo); lista vazia se não "
            "houver meta com data-alvo\n"
            "- performance_verdict: lista de frases avaliando a rentabilidade de cada "
            "investimento ou classe de ativo (use a variação de cota, rentabilidade do "
            "mês/ano e concentração do contexto de investimentos) e sinalizando quando "
            "vale considerar mover recursos para outra classe, sem citar fundo específico\n"
            "- contribution_rationale: lista de frases explicando o motivo do valor "
            "sugerido de aporte em cada classe do plano acima, sem alterar os valores\n"
        )

        payload = _ollama_post(
            f"{self.ollama_url}/api/generate",
            {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            model=self.chat_model,
            timeout=300,
        )

        content = payload.get("response", "{}")
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {"summary": content}

        report = normalize_executive_report(raw)
        report["sources"] = [
            {
                "source_type": item["chunk"].source_type,
                "source_id": item["chunk"].source_id,
                "similarity": round(item["similarity"], 4),
            }
            for item in context_chunks
            if item.get("chunk")
        ]
        return report

    def stream_chat_reply(self, context_chunks: list[dict], history: list, message: str):
        """Resposta conversacional em streaming, com memoria dos ultimos turnos.

        Ao contrario dos outros metodos desta classe, a resposta e texto livre
        (sem `format=json`): um chat nao tem um contrato de chaves fixas para a
        UI renderizar, so mostra o texto conforme chega. A checagem de conexao
        com o Ollama acontece de forma sincrona antes deste metodo devolver o
        gerador (dentro de `_ollama_stream_lines`), para o chamador poder
        responder 503 em vez de abrir um `StreamingHttpResponse` que falharia
        no meio.
        """
        context_text = "\n\n".join(
            f"[Fonte: {item['chunk'].source_type}/{item['chunk'].source_id}]\n"
            f"{item['chunk'].content}"
            for item in context_chunks
            if item.get("chunk")
        )
        history_text = "\n".join(
            f"{'Usuário' if entry.role == ChatMessageRole.USER else 'Assistente'}: {entry.content}"
            for entry in history
        )

        prompt = (
            "Você é um assistente financeiro pessoal, conversando em português do "
            "Brasil sobre os dados financeiros do próprio usuário.\n\n"
            "Regras obrigatórias:\n"
            "- Use apenas os dados fornecidos abaixo; nunca invente saldos, valores, "
            "instituições, fundos ou tickers.\n"
            "- Se a pergunta não puder ser respondida com os dados fornecidos, diga "
            "isso claramente em vez de inventar uma resposta.\n"
            "- Formate valores monetários no padrão brasileiro: separador de milhar "
            "'.', separador decimal ',' e prefixo 'R$ ' (ex.: R$ 1.234,56). Nunca use "
            "o padrão americano (1,234.56).\n"
            "- Isto não é recomendação de investimento; ao sugerir algo, fale em "
            "classes de ativo (ex.: Tesouro Selic, fundo multimercado, ETF de ações), "
            "nunca cite fundo ou ticker específico, pois você não tem dados de "
            "mercado atualizados.\n"
            "- Responda de forma direta e natural, como numa conversa, sem repetir a "
            "pergunta nem devolver JSON.\n\n"
            f"Dados financeiros do usuário:\n{context_text}\n\n"
        )
        if history_text:
            prompt += f"Histórico da conversa:\n{history_text}\n\n"
        prompt += f"Usuário: {message}\nAssistente:"

        lines = _ollama_stream_lines(
            f"{self.ollama_url}/api/generate",
            {
                "model": self.chat_model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.3},
            },
            model=self.chat_model,
            timeout=300,
        )
        return _iter_ollama_stream_text(lines)
