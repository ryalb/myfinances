import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

import requests
from django.db import transaction as db_transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from .consolidation import build_subscription_overview, build_user_financial_summary
from .models import (
    EMBEDDING_DIMENSIONS,
    Account,
    Card,
    CategorizationRule,
    Connection,
    DocumentChunk,
    DocumentChunkStatus,
    Embedding,
    FinancialGoal,
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


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list | tuple):
        return " ".join(_as_text(item) for item in value if _as_text(item))
    if isinstance(value, dict):
        return " ".join(_as_text(item) for item in value.values() if _as_text(item))
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
        if isinstance(item, dict):
            # `[{"acao": ..., "motivo": ...}]` acontece. Renderizar como
            # "[object Object]" seria pior que achatar em texto.
            text = " — ".join(_as_text(part) for part in item.values() if _as_text(part))
        else:
            text = _as_text(item)
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


def _build_summary_document(user) -> Document:
    summary = build_user_financial_summary(user)
    breakdown = summary["breakdown"]
    lines = [
        "# Resumo patrimonial",
        f"Ativos: {summary['assets']}",
        f"Passivos: {summary['liabilities']}",
        f"Patrimonio liquido: {summary['net_worth']}",
        "",
        "## Composicao",
        f"Caixa: {breakdown['cash']}",
        f"Investimentos: {breakdown['investments']}",
        f"Previdencia: {breakdown['pension']}",
        f"Dividas: {breakdown['debts']}",
        f"Cartoes de credito: {breakdown['credit_cards']}",
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
        lines.append(
            f"- {account.name} ({account.type}) em {account.connection.institution.name}: "
            f"saldo {account.balance}, disponivel {account.available_balance} {account.currency}"
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
        lines.append(
            f"- {card.name}: limite {card.credit_limit}, fatura atual {card.current_balance}, "
            f"vence dia {card.due_day}, fecha dia {card.close_day}"
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
    latest = {}
    for position in InvestmentPosition.objects.filter(investment__connection__user=user).order_by(
        "investment_id", "-as_of_date"
    ):
        latest.setdefault(position.investment_id, position)

    lines = [f"# Investimentos ({len(investments)})"]
    for investment in investments:
        position = latest.get(investment.pk)
        value = position.market_value if position else Decimal("0")
        as_of = f" em {position.as_of_date}" if position else " (sem posicao registrada)"
        lines.append(
            f"- {investment.name} ({investment.kind}): {value} {investment.currency}{as_of}"
        )
    return Document(
        source_type="investments",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(investments)},
    )


def _build_pension_document(user) -> Document | None:
    plans = list(PensionPlan.objects.filter(connection__user=user).order_by("name"))
    if not plans:
        return None
    lines = [f"# Previdencia privada ({len(plans)})"]
    for plan in plans:
        lines.append(f"- {plan.name} ({plan.provider}): saldo {plan.balance}")
    return Document(
        source_type="pension_plans",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(plans)},
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
            f"- {goal.name} [{goal.status}]: {goal.current_amount} de {goal.target_amount} "
            f"({progress:.1f}%){alvo}"
        )
    return Document(
        source_type="goals",
        source_id=str(user.pk),
        content="\n".join(lines),
        metadata={"count": len(goals)},
    )


def _build_subscriptions_document(user) -> Document | None:
    overview = build_subscription_overview(user)
    if not overview["active_count"]:
        return None
    lines = [
        "# Assinaturas e despesas recorrentes",
        f"Total recorrente mensal: {overview['monthly_recurring_total']} "
        f"em {overview['active_count']} assinaturas ativas",
        f"Pago no mes: {overview['paid_this_month']}",
        f"Pendente no mes: {overview['pending_this_month']}",
        f"Atrasado: {overview['overdue_total']}",
    ]
    if overview["overdue"]:
        lines.append("")
        lines.append("## Atrasados")
        for item in overview["overdue"]:
            lines.append(f"- {item['name']}: {item['amount']} venceu em {item['due_date']}")
    if overview["upcoming"]:
        lines.append("")
        lines.append("## Proximos vencimentos")
        for item in overview["upcoming"]:
            lines.append(f"- {item['name']}: {item['amount']} vence em {item['due_date']}")
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
        "description", "amount", "currency", "type", "category", "booked_at"
    ):
        rows = largest.setdefault(_month_key(tx.booked_at.date()), [])
        if len(rows) < 15:
            rows.append(tx)

    documents = []
    for month, bucket in totals.items():
        lines = [
            f"# Transacoes de {month} ({bucket['count']} lancamentos)",
            f"Receitas: {bucket['credits']}",
            f"Despesas: {bucket['debits']}",
            "",
            "## Despesas por categoria",
        ]
        for category, total in sorted(bucket["categories"].items(), key=lambda item: -item[1]):
            lines.append(f"- {category}: {total}")

        lines.append("")
        lines.append("## Maiores lancamentos")
        for tx in largest.get(month, []):
            lines.append(
                f"- {tx.booked_at:%Y-%m-%d} {tx.description}: {tx.amount} "
                f"{tx.currency} ({tx.type}, {tx.category or 'sem categoria'})"
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
        _build_goals_document,
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

        O resumo patrimonial entra sempre: e a ancora do relatorio e perderia a
        disputa de similaridade contra um mes de transacoes, que tem muito mais
        texto sobre qualquer assunto especifico.
        """
        anchor = list(
            Embedding.objects.filter(
                chunk__user=user,
                chunk__status=DocumentChunkStatus.INDEXED,
                chunk__source_type=SUMMARY_SOURCE_TYPE,
            ).select_related("chunk")[:1]
        )
        context = [{"chunk": row.chunk, "similarity": 1.0} for row in anchor]

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
            "Você é um assistente financeiro especializado. "
            "Com base nos dados reais do usuário abaixo, gere um relatório estruturado em JSON. "
            "Use apenas os dados fornecidos; não invente valores nem instituições.\n\n"
            f"Contexto:\n{context_text}\n\n"
            "Retorne um JSON com as chaves:\n"
            "- summary: resumo executivo da saúde financeira\n"
            "- strengths: lista de pontos fortes\n"
            "- weaknesses: lista de pontos fracos\n"
            "- adjustments: lista de ajustes sugeridos nas aplicações existentes\n"
            "- suggestions: lista de novas aplicações/investimentos sugeridas\n"
            "- projections: texto curto com projeções baseadas no comportamento histórico\n"
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
