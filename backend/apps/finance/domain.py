from decimal import Decimal

from .models import Account, AccountType, TransactionType

DEFAULT_CATEGORY = "uncategorized"

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "housing": ("aluguel", "condominio", "iptu", "moradia", "imobiliaria", "condo"),
    "food": (
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
    "transport": (
        "uber",
        "99",
        "combustivel",
        "posto",
        "pedagio",
        "transporte",
        "gasolina",
        "parcimetro",
    ),
    "health": ("farmacia", "hospital", "clinica", "plano de saude", "medico", "unimed", "amil"),
    "education": ("curso", "escola", "faculdade", "livro", "ensino", "treinamento"),
    "entertainment": (
        "cinema",
        "streaming",
        "spotify",
        "netflix",
        "show",
        "lazer",
        "ingresso",
        "ticketmaster",
    ),
    "investments": ("tesouro", "cdb", "fii", "acao", "fundos", "corretora", "broker", "dividend_"),
    "salary": ("salario", "pro-labore", "holerite", "pagamento", "pix_recebido"),
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


def normalize_transaction_category(description: str, provider_category: str, tx_type: str) -> str:
    # If the provider already gave a high-quality category, use it if it's not 'uncategorized'
    if provider_category and provider_category.lower() not in ("uncategorized", "none"):
        # Check if it matches any of our known categories or is a valid specific one
        return provider_category

    source = f"{description} {provider_category}".strip().lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in source for keyword in keywords):
            return category

    if tx_type == TransactionType.CREDIT:
        return "income"
    if tx_type == TransactionType.DEBIT:
        return "expenses"
    return DEFAULT_CATEGORY
