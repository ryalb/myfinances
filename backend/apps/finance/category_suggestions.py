"""Sugestao de categoria para transferencias PIX, a partir do nome da contraparte.

A Pluggy devolve "Pix" ou "Transferencia - PIX" para quase tudo que e transferencia,
e o nome de quem recebeu ou pagou e o que diz a categoria real ("Padaria X" e
"Mercado Y" sao despesas diferentes). A IA local sugere uma categoria a partir desse
nome.

Regras de seguranca do fluxo:

- A sugestao fica em `suggested_category` e nao altera `category`. So vira categoria
  quando o usuario aceita (`accept_suggestion`).
- Contraparte ja conhecida nao chama o modelo de novo: se outra transacao do mesmo
  usuario com o mesmo nome ja tem categoria manual ou sugestao, ela e reaproveitada.
- Nome de pessoa e dado pessoal: o prompt leva so o nome, a descricao e o tipo.
  Documento (CPF/CNPJ) nao entra.
- Inferencia so em host local, pela mesma checagem do resto da IA.
"""

import json
import os
import unicodedata
from dataclasses import dataclass

from django.db import transaction as db_transaction

from .ai_services import _ollama_post, assert_local_inference
from .categories import PLUGGY_CATEGORY_PT
from .filters import user_transactions
from .models import CategorizationRule, Transaction, TransactionType

# Categorias que nao dizem nada sobre o gasto: so transacoes com uma delas sao
# candidatas a sugestao. Categoria real da Pluggy (ex.: "Supermercado") e preservada.
GENERIC_CATEGORIES = frozenset(
    {"", "pix", "transferência - pix", "transferências", "outros", "sem categoria"}
)

# Nunca sugeridas: transferencia entre contas proprias nao e gasto, e as genericas
# nao ajudam o usuario a decidir.
EXCLUDED_SUGGESTIONS = frozenset(
    {
        "transferência entre contas próprias",
        "transferências",
        "pix",
        "transferência - pix",
        "outros",
        "sem categoria",
    }
)

DEFAULT_LIMIT = 30
MAX_LIMIT = 100


@dataclass(frozen=True)
class CategoryPrediction:
    category: str
    confidence: float


@dataclass
class BatchResult:
    suggested: int = 0
    reused: int = 0
    unmatched: int = 0
    calls: int = 0


def allowed_categories() -> dict[str, str]:
    """Mapa minusculo -> nome canonico das categorias que a IA pode devolver."""
    values = {
        value
        for value in PLUGGY_CATEGORY_PT.values()
        if value.strip().lower() not in EXCLUDED_SUGGESTIONS
    }
    return {value.lower(): value for value in sorted(values)}


def is_pix(tx: Transaction) -> bool:
    haystack = " ".join(
        [tx.payment_method, tx.operation_type, tx.description, tx.provider_category]
    ).lower()
    return "pix" in haystack


def is_generic_category(category: str) -> bool:
    return category.strip().lower() in GENERIC_CATEGORIES


def counterparty_name(tx: Transaction) -> str:
    """Quem recebeu (saida) ou pagou (entrada). Vazio quando a Pluggy nao informa."""
    if tx.type == TransactionType.DEBIT:
        parties = (tx.payment_receiver, tx.payment_payer)
    else:
        parties = (tx.payment_payer, tx.payment_receiver)
    for party in parties:
        name = party.get("name") if isinstance(party, dict) else None
        if isinstance(name, str) and name.strip():
            return " ".join(name.split())
    return ""


def normalize_name(raw: str) -> str:
    """Chave de agrupamento: sem acento, maiuscula, espacos colapsados."""
    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.upper().split())


def build_prompt(name: str, description: str, tx_type: str, categories: list[str]) -> str:
    direction = (
        "saída (o usuário pagou)"
        if tx_type == TransactionType.DEBIT
        else "entrada (o usuário recebeu)"
    )
    options = "\n".join(f"- {category}" for category in categories)
    return (
        "Você classifica transferências PIX de uma conta bancária brasileira.\n"
        "Dado o nome da contraparte, escolha UMA categoria da lista abaixo.\n\n"
        "Regras:\n"
        "- Use somente categorias da lista, escritas exatamente como estão.\n"
        "- Se o nome for uma pessoa e nada indicar o gasto, responda category null "
        "com confidence baixa.\n"
        "- Nomes de empresas (padaria, farmácia, posto, app) indicam a categoria "
        "com mais precisão.\n\n"
        f"Tipo: {direction}\n"
        f"Contraparte: {name}\n"
        f"Descrição do banco: {description}\n\n"
        f"Categorias:\n{options}\n\n"
        'Responda apenas JSON: {"category": "<categoria ou null>", "confidence": <0 a 1>}'
    )


def parse_suggestion(raw_text: str, allowed: dict[str, str]) -> CategoryPrediction | None:
    """Valida a resposta do modelo. Qualquer coisa fora do contrato vira None.

    `allowed` garante que a categoria exista na taxonomia: resposta inventada pelo
    modelo nao chega ao banco.
    """
    try:
        data = json.loads(raw_text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    category = data.get("category")
    if not isinstance(category, str):
        return None
    canonical = allowed.get(category.strip().lower())
    if canonical is None:
        return None

    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        return None
    if confidence != confidence:  # NaN
        return None
    return CategoryPrediction(category=canonical, confidence=min(max(confidence, 0.0), 1.0))


class CategorySuggester:
    """Cliente do modelo local. Levanta AIServiceUnavailable se nao puder rodar."""

    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv(
            "OLLAMA_CATEGORY_MODEL", os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:14b")
        )
        assert_local_inference(self.ollama_url)
        self.allowed = allowed_categories()
        self.categories = sorted(self.allowed.values())

    def predict(self, name: str, description: str, tx_type: str) -> CategoryPrediction | None:
        payload = _ollama_post(
            f"{self.ollama_url}/api/generate",
            {
                "model": self.model,
                "prompt": build_prompt(name, description, tx_type, self.categories),
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            model=self.model,
            timeout=60,
        )
        return parse_suggestion(str(payload.get("response", "")), self.allowed)


def suggest_categories(
    user, suggester: CategorySuggester, limit: int = DEFAULT_LIMIT
) -> BatchResult:
    """Preenche `suggested_category` nas transacoes PIX candidatas do usuario.

    `limit` limita chamadas ao modelo, nao reaproveitamentos: custo e tempo ficam
    previsiveis mesmo com um historico grande.
    """
    limit = max(0, min(limit, MAX_LIMIT))
    result = BatchResult()
    transactions = list(user_transactions(user).order_by("-booked_at"))

    known: dict[str, CategoryPrediction] = {}
    pix_rows: list[tuple[Transaction, str]] = []
    for tx in transactions:
        if not is_pix(tx):
            continue
        key = normalize_name(counterparty_name(tx))
        if not key:
            continue
        pix_rows.append((tx, key))
        if tx.category_is_manual and tx.category:
            known.setdefault(key, CategoryPrediction(tx.category, 1.0))
        elif tx.suggested_category:
            known.setdefault(
                key,
                CategoryPrediction(tx.suggested_category, tx.suggested_category_confidence or 0.0),
            )

    unmatched_keys: set[str] = set()
    updated: list[Transaction] = []
    for tx, key in pix_rows:
        if tx.category_is_manual or tx.suggested_category or not is_generic_category(tx.category):
            continue

        if key in known:
            prediction = known[key]
            result.reused += 1
        elif key in unmatched_keys:
            result.unmatched += 1
            continue
        elif result.calls >= limit:
            continue
        else:
            # AIServiceUnavailable propaga: se o modelo caiu, o lote para inteiro.
            result.calls += 1
            prediction = suggester.predict(counterparty_name(tx), tx.description, tx.type)
            if prediction is None:
                unmatched_keys.add(key)
                result.unmatched += 1
                continue
            known[key] = prediction
            result.suggested += 1

        tx.suggested_category = prediction.category
        tx.suggested_category_confidence = prediction.confidence
        updated.append(tx)

    if updated:
        with db_transaction.atomic():
            Transaction.objects.bulk_update(
                updated, ["suggested_category", "suggested_category_confidence"]
            )
    return result


def accept_suggestion(tx: Transaction, user) -> Transaction:
    """Aplica a sugestao como escolha manual e cria regra para a contraparte.

    A regra faz as proximas transacoes com esse nome (sync ou "reaplicar regras")
    cairem na mesma categoria, sem nova chamada ao modelo.
    """
    category = tx.suggested_category
    name = counterparty_name(tx)

    tx.category = category
    tx.category_is_manual = True
    tx.suggested_category = ""
    tx.suggested_category_confidence = None

    with db_transaction.atomic():
        tx.save(
            update_fields=[
                "category",
                "category_is_manual",
                "suggested_category",
                "suggested_category_confidence",
            ]
        )
        if name and not CategorizationRule.objects.filter(user=user, pattern__iexact=name).exists():
            CategorizationRule.objects.create(user=user, pattern=name.lower(), category=category)
    return tx
