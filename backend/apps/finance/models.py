from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from pgvector.django import HnswIndex, VectorField


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class FinancialInstitution(TimeStampedModel):
    name = models.CharField(max_length=255)
    provider_id = models.CharField(max_length=255, unique=True)
    logo_url = models.URLField(blank=True)

    def __str__(self) -> str:
        return self.name


class ConnectionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    ERROR = "error", "Error"
    EXPIRED = "expired", "Expired"


class Connection(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connections"
    )
    institution = models.ForeignKey(
        FinancialInstitution, on_delete=models.PROTECT, related_name="connections"
    )
    external_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20, choices=ConnectionStatus.choices, default=ConnectionStatus.PENDING
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.institution.name}"


class Identity(TimeStampedModel):
    """Titular do item na Pluggy (`GET /identity`).

    Uma identidade por item, nao por conta: a Pluggy devolve o titular pelo
    itemId, e todas as contas do item pertencem a mesma pessoa.
    """

    connection = models.OneToOneField(
        Connection, on_delete=models.CASCADE, related_name="identity"
    )
    external_id = models.CharField(max_length=255, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    document = models.CharField(max_length=32, blank=True)
    document_type = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    job_title = models.CharField(max_length=255, blank=True)
    email = models.EmailField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=500, blank=True)
    # Campos crus da Pluggy sem uso hoje na tela, mas uteis para o relatorio de
    # IA (perfil de investidor e renda/patrimonio declarados ao banco).
    investor_profile = models.CharField(max_length=20, blank=True)
    sex = models.CharField(max_length=10, blank=True)
    marital_status = models.CharField(max_length=50, blank=True)
    social_name = models.CharField(max_length=255, blank=True)
    occupation_description = models.CharField(max_length=255, blank=True)
    informed_income_amount = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    informed_income_frequency = models.CharField(max_length=20, blank=True)
    informed_patrimony_amount = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )

    def __str__(self) -> str:
        return self.full_name or f"Identity {self.external_id}"


class AccountType(models.TextChoices):
    CHECKING = "checking", "Checking"
    SAVINGS = "savings", "Savings"
    BROKERAGE = "brokerage", "Brokerage"
    CREDIT = "credit", "Credit"
    OTHER = "other", "Other"


class Account(TimeStampedModel):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="accounts")
    external_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    # Numero da conta para transferencia (Pluggy `bankData.transferNumber`).
    # Alguns bancos devolvem `name` generico ("Conta Corrente") para toda conta
    # do mesmo tipo; sem isto, duas contas do usuario ficam indistinguiveis na UI.
    number = models.CharField(max_length=32, blank=True)
    type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.OTHER)
    currency = models.CharField(max_length=3, default="BRL")
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    # Campos crus da Pluggy (`subtype`, `marketingName`, `owner`, `taxNumber`,
    # `bankData.*`) sem uso hoje na tela, mas uteis para o relatorio de IA
    # (ex: limite de cheque especial usado, saldo com transacoes nao compensadas).
    subtype = models.CharField(max_length=30, blank=True)
    marketing_name = models.CharField(max_length=255, blank=True)
    owner_name = models.CharField(max_length=255, blank=True)
    tax_number = models.CharField(max_length=32, blank=True)
    closing_balance = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    overdraft_limit = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    overdraft_used = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class Card(TimeStampedModel):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="cards")
    external_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    last4 = models.CharField(max_length=4, blank=True)
    credit_limit = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    due_day = models.PositiveSmallIntegerField(null=True, blank=True)
    close_day = models.PositiveSmallIntegerField(null=True, blank=True)
    # Campos crus de `creditData` na Pluggy, sem uso hoje na tela mas uteis para
    # o relatorio de IA (ex: alertar cartao bloqueado, limite disponivel real).
    brand = models.CharField(max_length=50, blank=True)
    level = models.CharField(max_length=50, blank=True)
    available_credit_limit = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    minimum_payment = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    is_limit_flexible = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=20, blank=True)
    holder_type = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return self.name


class TransactionType(models.TextChoices):
    DEBIT = "debit", "Debit"
    CREDIT = "credit", "Credit"


class Transaction(TimeStampedModel):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="transactions", null=True, blank=True
    )
    card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name="transactions", null=True, blank=True
    )
    external_id = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="BRL")
    type = models.CharField(max_length=10, choices=TransactionType.choices)
    category = models.CharField(max_length=100, blank=True)
    provider_category = models.CharField(max_length=100, blank=True)
    booked_at = models.DateTimeField()
    # Campos crus da Pluggy sem uso hoje na tela, mas uteis para o relatorio de
    # IA (ex: identificar parcelamento, contraparte do PIX, estabelecimento).
    description_raw = models.CharField(max_length=500, blank=True)
    amount_in_account_currency = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    balance_after = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    provider_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, blank=True)
    operation_type = models.CharField(max_length=50, blank=True)
    operation_type_additional_info = models.CharField(max_length=255, blank=True)
    provider_transaction_id = models.CharField(max_length=255, blank=True)
    merchant_name = models.CharField(max_length=255, blank=True)
    merchant_business_name = models.CharField(max_length=255, blank=True)
    merchant_cnpj = models.CharField(max_length=32, blank=True)
    merchant_cnae = models.CharField(max_length=32, blank=True)
    installment_number = models.PositiveSmallIntegerField(null=True, blank=True)
    installment_total = models.PositiveSmallIntegerField(null=True, blank=True)
    installment_total_amount = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    purchase_date = models.DateTimeField(null=True, blank=True)
    payee_mcc = models.CharField(max_length=10, blank=True)
    bill_id = models.CharField(max_length=255, blank=True)
    bill_forecast_date = models.CharField(max_length=7, blank=True)
    payment_method = models.CharField(max_length=20, blank=True)
    payment_reason = models.CharField(max_length=255, blank=True)
    payment_reference_number = models.CharField(max_length=255, blank=True)
    payment_authentication_code = models.CharField(max_length=255, blank=True)
    # `payer`/`receiver` variam de formato conforme o metodo (PIX/TED/boleto);
    # JSON em vez de colunas porque nao ha um schema fixo entre eles.
    payment_payer = models.JSONField(default=dict, blank=True)
    payment_receiver = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-booked_at"]

    def __str__(self) -> str:
        return self.description

    @property
    def is_internal_transfer(self) -> bool:
        from django.conf import settings

        category = self.provider_category.strip().lower()
        return category in settings.FINANCE_INTERNAL_TRANSFER_CATEGORIES


class Investment(TimeStampedModel):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="investments")
    external_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default="BRL")
    # Campos crus da Pluggy sem uso hoje na tela, mas uteis para o relatorio de
    # IA (ex: vencimento de renda fixa, isencao de IR, identificacao do ativo).
    subtype = models.CharField(max_length=50, blank=True)
    number = models.CharField(max_length=100, blank=True)
    isin = models.CharField(max_length=20, blank=True)
    code = models.CharField(max_length=100, blank=True)
    issuer = models.CharField(max_length=255, blank=True)
    issuer_cnpj = models.CharField(max_length=32, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    rate_type = models.CharField(max_length=50, blank=True)
    tax_exempt = models.BooleanField(null=True, blank=True)
    rate_periodicity = models.CharField(max_length=20, blank=True)
    indexer_additional_info = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return self.name


class InvestmentPosition(TimeStampedModel):
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name="positions")
    as_of_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    unit_price = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    market_value = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    # Rentabilidade/estado do dia da posicao (campos crus da Pluggy). Ficam na
    # posicao, nao no Investment, porque mudam a cada sincronizacao.
    last_month_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    last_twelve_months_rate = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    annual_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    fixed_annual_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    amount_profit = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_withdrawal = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_original = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    price_factor = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=20, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    grace_period_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("investment", "as_of_date")


class PensionPlan(TimeStampedModel):
    # Nulo para plano cadastrado manualmente: previdencia privada (PGBL/VGBL) fica
    # no Open Insurance (Susep), fora do Open Finance que a Pluggy cobre, entao a
    # seguradora raramente aparece sincronizada via `connection`.
    connection = models.ForeignKey(
        Connection, on_delete=models.CASCADE, related_name="pension_plans", null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pension_plans"
    )
    external_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=255)
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    # Rentabilidade da previdencia (campos crus da Pluggy), util para o
    # relatorio de IA comparar contra os demais investimentos.
    annual_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    amount_profit = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_original = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)


class NetWorthSnapshot(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="net_worth_snapshots"
    )
    date = models.DateField()
    assets = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    liabilities = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    net_worth = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]


class GoalStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ACHIEVED = "achieved", "Achieved"
    PAUSED = "paused", "Paused"


class FinancialGoal(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="financial_goals"
    )
    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=16, decimal_places=2)
    current_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=GoalStatus.choices, default=GoalStatus.ACTIVE)


class SyncJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class SyncJob(TimeStampedModel):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="sync_jobs")
    kind = models.CharField(max_length=50, default="full")
    status = models.CharField(
        max_length=20, choices=SyncJobStatus.choices, default=SyncJobStatus.QUEUED
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class CategorizationRule(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categorization_rules"
    )
    pattern = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "-created_at"]


class SubscriptionCategory(models.TextChoices):
    UTILITIES = "utilities", "Utilities"
    INTERNET = "internet", "Internet"
    PHONE = "phone", "Phone"
    STREAMING = "streaming", "Streaming"
    OTHER = "other", "Other"


class SubscriptionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"


class Subscription(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    connection = models.ForeignKey(
        Connection, on_delete=models.CASCADE, related_name="subscriptions", null=True, blank=True
    )
    name = models.CharField(max_length=255)
    category = models.CharField(
        max_length=50,
        choices=SubscriptionCategory.choices,
        default=SubscriptionCategory.OTHER,
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    # Sem os validators, um due_day fora do calendario nao estoura: o
    # `_due_date_for` do reconcile cai no dia 28 e o vencimento vira outro em
    # silencio. O DRF herda estes validators e responde 400.
    due_day = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    payment_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriptions"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class SubscriptionPayment(TimeStampedModel):
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payments"
    )
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.PENDING
    )
    paid_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    # Transacao que o reconcile usou para marcar como pago -- sem isto o "pago"
    # nao e verificavel: paid_date/paid_amount sao copias, o vinculo com a
    # Transaction original se perdia. Nunca gravado em marcacao manual.
    matched_transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subscription_payments",
    )

    class Meta:
        ordering = ["-due_date"]
        unique_together = ("subscription", "due_date")


class DocumentChunkStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    INDEXED = "indexed", "Indexed"
    FAILED = "failed", "Failed"


# nomic-embed-text produz 768 dimensoes. A coluna do pgvector tem dimensao fixa,
# entao trocar OLLAMA_EMBEDDING_MODEL por um modelo de outra dimensao exige
# migration. O RAGService confere o tamanho antes de gravar para a falha aparecer
# como erro claro em vez de erro do banco.
EMBEDDING_DIMENSIONS = 768


class DocumentChunk(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_chunks"
    )
    source_type = models.CharField(max_length=50)
    source_id = models.CharField(max_length=255)
    content = models.TextField()
    # Digest do conteudo. Serve para reindexar so o que mudou: sem isso cada
    # relatorio gerado reembedava todos os dominios do usuario.
    content_hash = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=DocumentChunkStatus.choices, default=DocumentChunkStatus.PENDING
    )
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "source_type", "source_id"]),
        ]
        # A trinca identifica o documento. Sem a constraint o `update_or_create`
        # nao tem o que travar e duas requisicoes concorrentes recriam o chunk.
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source_type", "source_id"],
                name="unique_document_chunk_per_source",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id}"


class Embedding(TimeStampedModel):
    chunk = models.OneToOneField(DocumentChunk, on_delete=models.CASCADE, related_name="embedding")
    vector = VectorField(dimensions=EMBEDDING_DIMENSIONS)
    model = models.CharField(max_length=100, default="nomic-embed-text")

    class Meta:
        indexes = [
            models.Index(fields=["chunk"]),
            # HNSW para distancia de cosseno: e o operador que a busca usa
            # (`CosineDistance`). Um indice com a classe de operador errada e
            # simplesmente ignorado pelo planner.
            HnswIndex(
                name="embedding_vector_hnsw",
                fields=["vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]


class PortfolioReport(TimeStampedModel):
    """Relatorio de IA gerado por `LLMService.generate_portfolio_report`.

    Sem persistir, cada relatorio existia so no `ref` do frontend: um refresh de
    pagina ou fechar a aba perdia a analise, e nao havia como comparar com uma
    geracao anterior.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolio_reports"
    )
    query = models.CharField(max_length=500, blank=True)
    summary = models.TextField(blank=True)
    projections = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    adjustments = models.JSONField(default=list, blank=True)
    suggestions = models.JSONField(default=list, blank=True)
    disclaimer = models.TextField(blank=True)
    # Fontes (DocumentChunk) usadas na geracao, com a similaridade de cada uma.
    # Guardado como snapshot: os chunks originais podem mudar ou ser removidos
    # depois, e o relatorio precisa continuar mostrando o que foi usado na epoca.
    sources = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.created_at:%Y-%m-%d %H:%M}"


class ProcessedWebhookEvent(TimeStampedModel):
    """Registro de eventId ja processado.

    A Pluggy reentrega webhooks ate 9 vezes; sem isso cada reentrega
    reprocessaria o evento (refetch e reescrita dos mesmos dados).
    """

    event_id = models.CharField(max_length=255, unique=True)
    event = models.CharField(max_length=100)
    item_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.event}:{self.event_id}"
