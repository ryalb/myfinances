import json
import os
from decimal import Decimal

import requests

from .consolidation import build_user_financial_summary
from .models import (
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
)


def _build_user_context(user) -> str:
    summary = build_user_financial_summary(user)
    accounts = Account.objects.filter(connection__user=user).select_related("connection")
    cards = Card.objects.filter(connection__user=user)
    investments = Investment.objects.filter(connection__user=user)
    positions = InvestmentPosition.objects.filter(investment__connection__user=user).order_by(
        "-as_of_date"
    )
    pensions = PensionPlan.objects.filter(connection__user=user)
    goals = FinancialGoal.objects.filter(user=user)
    rules = CategorizationRule.objects.filter(user=user, is_active=True).order_by(
        "priority", "-created_at"
    )
    connections = Connection.objects.filter(user=user).select_related("institution")

    lines = [
        "# Resumo Financeiro",
        f"Ativos: {summary['assets']}",
        f"Passivos: {summary['liabilities']}",
        f"Patrimônio líquido: {summary['net_worth']}",
        "",
        f"## Contas ({accounts.count()})",
    ]
    for account in accounts:
        lines.append(
            f"- {account.name} ({account.type}): saldo {account.balance}, "
            f"disponível {account.available_balance} {account.currency}"
        )

    lines.append("")
    lines.append(f"## Cartões ({cards.count()})")
    for card in cards:
        lines.append(
            f"- {card.name}: limite {card.credit_limit}, saldo atual {card.current_balance}"
        )

    lines.append("")
    lines.append(f"## Investimentos ({investments.count()})")
    for investment in investments:
        position = positions.filter(investment=investment).first()
        market_value = position.market_value if position else Decimal("0")
        lines.append(
            f"- {investment.name} ({investment.kind}): {market_value} {investment.currency}"
        )

    lines.append("")
    lines.append(f"## Previdência ({pensions.count()})")
    for pension in pensions:
        lines.append(f"- {pension.name} ({pension.provider}): {pension.balance}")

    lines.append("")
    lines.append(f"## Metas ({goals.count()})")
    for goal in goals:
        progress = (
            float((goal.current_amount / goal.target_amount) * 100) if goal.target_amount > 0 else 0
        )
        lines.append(
            f"- {goal.name}: {goal.current_amount} / {goal.target_amount} ({progress:.1f}%)"
        )

    lines.append("")
    lines.append(f"## Regras de Categorização ({rules.count()})")
    for rule in rules:
        lines.append(f"- {rule.pattern} -> {rule.category} (prioridade {rule.priority})")

    lines.append("")
    lines.append(f"## Conexões ({connections.count()})")
    for connection in connections:
        lines.append(
            f"- {connection.institution.name}: status {connection.status}, "
            f"última sync {connection.last_synced_at}"
        )

    return "\n".join(lines)


class RAGService:
    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.chat_model = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:14b")

    def _get_embedding(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.ollama_url}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def index_user_context(self, user) -> None:
        context = _build_user_context(user)
        chunk = DocumentChunk.objects.create(
            user=user,
            source_type="financial_summary",
            source_id=str(user.id),
            content=context,
            metadata={"generated_at": __import__("django").utils.timezone.now().isoformat()},
            status=DocumentChunkStatus.INDEXED,
            indexed_at=__import__("django").utils.timezone.now(),
        )
        vector = self._get_embedding(context)
        Embedding.objects.create(chunk=chunk, vector=vector, model=self.embedding_model)

    def search(self, user, query: str, top_k: int = 5) -> list[dict]:
        query_vector = self._get_embedding(query)
        chunks = DocumentChunk.objects.filter(user=user, status=DocumentChunkStatus.INDEXED)
        results = []
        for chunk in chunks:
            embedding = getattr(chunk, "embedding", None)
            if not embedding:
                continue
            similarity = self._cosine_similarity(query_vector, embedding.vector)
            if similarity > 0:
                results.append({"chunk": chunk, "similarity": similarity})
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        import math

        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class LLMService:
    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.chat_model = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:14b")

    def generate_portfolio_report(self, user, context_chunks: list[dict]) -> dict:
        context_text = "\n\n".join(
            f"[Fonte: {item['chunk'].source_type}]\n{item['chunk'].content}"
            for item in context_chunks
            if item.get("chunk")
        )

        prompt = (
            "Você é um assistente financeiro especializado. "
            "Com base nos dados reais do usuário abaixo, gere um relatório estruturado em JSON.\n\n"
            f"Contexto:\n{context_text}\n\n"
            "Retorne um JSON com as chaves:\n"
            "- summary: resumo executivo da saúde financeira\n"
            "- strengths: lista de pontos fortes\n"
            "- weaknesses: lista de pontos fracos\n"
            "- adjustments: lista de ajustes sugeridos nas aplicações existentes\n"
            "- suggestions: lista de novas aplicações/investimentos sugeridas\n"
            "- projections: texto curto com projeções baseadas no comportamento histórico\n"
            "- sources: lista dos tipos de fonte usados\n"
        )

        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            timeout=120,
        )
        response.raise_for_status()
        content = response.json().get("response", "{}")
        try:
            return json.loads(content)
        except Exception:
            return {
                "summary": content,
                "strengths": [],
                "weaknesses": [],
                "adjustments": [],
                "suggestions": [],
                "projections": "",
                "sources": [],
            }
