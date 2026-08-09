import logging
import re
from collections.abc import Iterable
from decimal import Decimal

from django.db.models import Q
from django.utils.text import slugify

from .categories import (
    CATEGORY_EXPENSES,
    CATEGORY_INCOME,
    CATEGORY_UNCATEGORIZED,
    translate_category,
)
from .models import Account, AccountType, CategorizationRule, FinancialInstitution, TransactionType

logger = logging.getLogger(__name__)


def get_or_create_institution(item_data: dict) -> FinancialInstitution:
    connector = item_data.get("connector", {}) or {}
    provider_id = (
        item_data.get("institutionId")
        or item_data.get("connectorId")
        or connector.get("id")
        or "unknown"
    )
    name = (
        connector.get("name")
        or item_data.get("name")
        or (
            f"Instituição {provider_id}"
            if str(provider_id) != "unknown"
            else "Instituição não identificada"
        )
    )
    institution, _ = FinancialInstitution.objects.get_or_create(
        provider_id=str(provider_id),
        defaults={"name": name},
    )
    if (
        institution.name.startswith("Instituição ")
        and name != institution.name
        and not name.startswith("Instituição ")
    ):
        institution.name = name
        institution.save(update_fields=["name"])
    return institution


DEFAULT_CATEGORY = CATEGORY_UNCATEGORIZED

# Items do Meu Pluggy sempre chegam com connectorId=200 e connector.name="MeuPluggy",
# qualquer que seja o banco por tras. Sem isto, todas as conexoes colapsam numa
# unica instituicao chamada "MeuPluggy" e a UI mostra cards identicos.
# O nome do banco real so aparece nos nomes das contas e cartoes.
INSTITUTION_KEYWORDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "nubank": ("Nubank", ("nubank", "nu pagamentos", "ultraviolet", "ultravioleta")),
    "rico": ("Rico Investimentos", ("rico",)),
    "itau": ("Itaú", ("itau", "itaú", "iti")),
    "bradesco": ("Bradesco", ("bradesco", "next")),
    "santander": ("Santander", ("santander",)),
    "banco-do-brasil": ("Banco do Brasil", ("banco do brasil", "bb ")),
    "caixa": ("Caixa Econômica", ("caixa economica", "caixa econômica")),
    "inter": ("Banco Inter", ("banco inter", "inter ")),
    "c6": ("C6 Bank", ("c6 bank", "c6bank", "banco c6")),
    "xp": ("XP Investimentos", ("xp investimentos", "xp inc")),
    "btg": ("BTG Pactual", ("btg",)),
    "sicredi": ("Sicredi", ("sicredi",)),
    "sicoob": ("Sicoob", ("sicoob",)),
    "safra": ("Banco Safra", ("safra",)),
    "original": ("Banco Original", ("banco original",)),
    "neon": ("Neon", ("neon",)),
    "picpay": ("PicPay", ("picpay",)),
    "pagbank": ("PagBank", ("pagbank", "pagseguro")),
    "mercadopago": ("Mercado Pago", ("mercado pago", "mercadopago")),
    "clear": ("Clear", ("clear corretora",)),
    "modalmais": ("Modalmais", ("modalmais", "modal mais")),
}


def derive_institution_from_names(candidates: Iterable[str]) -> tuple[str, str] | None:
    """Match account/card names against known institutions.

    Returns (key, display_name), or None when nothing matches.
    """
    source = " ".join((c or "").lower() for c in candidates)
    if not source.strip():
        return None
    for key, (display, keywords) in INSTITUTION_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword.strip())}\b", source):
                return key, display
    return None


def refine_connection_institution(connection) -> FinancialInstitution | None:
    """Repoint a Connection at an institution derived from its synced accounts.

    Safe to call repeatedly: the derived provider_id is namespaced under the
    original one (e.g. `200:nubank`), and the namespace is not re-nested.
    """
    account_names = list(connection.accounts.values_list("name", flat=True))
    card_names = list(connection.cards.values_list("name", flat=True))
    if not account_names and not card_names:
        logger.info(
            "Institution not derived for connection %s: no accounts or cards yet",
            connection.external_id,
        )
        return None

    current = connection.institution
    base = str(current.provider_id).split(":")[0] if current else "unknown"

    derived = derive_institution_from_names(account_names + card_names)
    if derived:
        key, display = derived
    else:
        bank_names = list(
            connection.accounts.exclude(type=AccountType.CREDIT).values_list("name", flat=True)
        )
        display = next(
            (n.split(" - ")[0].strip() for n in (bank_names or account_names or card_names) if n),
            "",
        )
        if not display:
            logger.warning(
                "Institution not derived for connection %s: no usable name in %s",
                connection.external_id,
                account_names + card_names,
            )
            return None
        key = slugify(display) or "desconhecida"
        logger.info(
            "Institution for connection %s fell back to the account name %r "
            "(no keyword matched %s)",
            connection.external_id,
            display,
            account_names + card_names,
        )

    provider_id = f"{base}:{key}"
    institution, _ = FinancialInstitution.objects.get_or_create(
        provider_id=provider_id,
        defaults={"name": display},
    )
    if institution.name != display:
        institution.name = display
        institution.save(update_fields=["name"])

    if connection.institution_id != institution.id:
        connection.institution = institution
        connection.save(update_fields=["institution", "updated_at"])

    logger.info(
        "Institution derived for connection %s: %r (provider_id=%s) from %s",
        connection.external_id,
        display,
        provider_id,
        account_names + card_names,
    )
    return institution


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Moradia": ("aluguel", "condominio", "iptu", "moradia", "imobiliaria", "condo"),
    "Alimentação": (
        "mercado",
        "supermercado",
        "restaurante",
        "ifood",
        "lanche",
        "iFood",
        "fast food",
        "padaria",
        "cafe",
    ),
    "Transporte": (
        "uber",
        "99",
        "combustivel",
        "posto",
        "pedagio",
        "transporte",
        "gasolina",
        "parcimetro",
    ),
    "Saúde": ("farmacia", "hospital", "clinica", "plano de saude", "medico", "unimed", "amil"),
    "Educação": ("curso", "escola", "faculdade", "livro", "ensino", "treinamento"),
    "Lazer": (
        "cinema",
        "streaming",
        "spotify",
        "netflix",
        "show",
        "lazer",
        "ingresso",
        "ticketmaster",
    ),
    "Investimentos": (
        "tesouro",
        "cdb",
        "fii",
        "acao",
        "fundos",
        "corretora",
        "broker",
        "dividend_",
    ),
    "Salário": ("salario", "pro-labore", "holerite", "pagamento", "pix_recebido"),
}


def classify_account_balance(account: Account) -> tuple[str, Decimal]:
    balance = account.available_balance
    if account.type in (AccountType.CHECKING, AccountType.SAVINGS):
        return "cash", balance
    if account.type == AccountType.BROKERAGE:
        return "investments", balance
    if account.type == AccountType.CREDIT:
        return "credit_cards", balance.copy_abs()
    return "cash", balance


def _match_keyword_category(description: str, provider_category: str) -> str | None:
    source = f"{description} {provider_category}".strip().lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in source for keyword in keywords):
            return category
    return None


def match_categorization_rule(description: str, provider_category: str, rules) -> str | None:
    """Primeira regra que casa, na ordem de prioridade recebida.

    Recebe `rules` ja materializado para a reaplicacao em lote poder ler as regras
    uma unica vez em vez de uma query por transacao.
    """
    source = f"{description} {provider_category}".strip().lower()
    for rule in rules:
        if slugify(rule.pattern) in source or rule.pattern.lower() in source:
            return rule.category
    return None


def active_categorization_rules(user):
    return list(
        CategorizationRule.objects.filter(
            Q(user=user) | Q(user__isnull=True),
            is_active=True,
        ).order_by("priority", "-created_at")
    )


def normalize_transaction_category(
    description: str,
    provider_category: str,
    tx_type: str,
    user=None,
    rules=None,
) -> str:
    # Regra do usuario vem primeiro, antes do `provider_category`.
    #
    # A ordem era o inverso, e isso fazia o motor de regras parecer quebrado: uma
    # regra "uber -> transporte" nunca se aplicava porque a Pluggy manda "Travel",
    # ou seja, intencao explicita do usuario perdia para heuristica do provedor.
    if user is not None or rules is not None:
        applicable = active_categorization_rules(user) if rules is None else rules
        matched = match_categorization_rule(description, provider_category, applicable)
        if matched:
            return matched

    if provider_category and provider_category.lower() not in ("uncategorized", "none"):
        # A taxonomia da Pluggy e em ingles; traduz na entrada para que tela,
        # export, filtro e relatorio de IA mostrem o mesmo texto em pt-BR.
        # `provider_category` guarda o valor cru como trilha de origem.
        return translate_category(provider_category)

    keyword_category = _match_keyword_category(description, provider_category)
    if keyword_category:
        return keyword_category

    if tx_type == TransactionType.CREDIT:
        return CATEGORY_INCOME
    if tx_type == TransactionType.DEBIT:
        return CATEGORY_EXPENSES
    return DEFAULT_CATEGORY
