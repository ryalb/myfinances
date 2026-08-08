from django.conf import settings
from django.db import models


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
    type = models.CharField(max_length=20, choices=AccountType.choices, default=AccountType.OTHER)
    currency = models.CharField(max_length=3, default="BRL")
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)

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

    class Meta:
        ordering = ["-booked_at"]

    def __str__(self) -> str:
        return self.description


class Investment(TimeStampedModel):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="investments")
    external_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default="BRL")

    def __str__(self) -> str:
        return self.name


class InvestmentPosition(TimeStampedModel):
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name="positions")
    as_of_date = models.DateField()
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    unit_price = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    market_value = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        unique_together = ("investment", "as_of_date")


class PensionPlan(TimeStampedModel):
    connection = models.ForeignKey(
        Connection, on_delete=models.CASCADE, related_name="pension_plans"
    )
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=255)
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)


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
    due_day = models.PositiveSmallIntegerField()
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

    class Meta:
        ordering = ["-due_date"]
        unique_together = ("subscription", "due_date")


class DocumentChunkStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    INDEXED = "indexed", "Indexed"
    FAILED = "failed", "Failed"


class DocumentChunk(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_chunks"
    )
    source_type = models.CharField(max_length=50)
    source_id = models.CharField(max_length=255)
    content = models.TextField()
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


class Embedding(TimeStampedModel):
    chunk = models.OneToOneField(DocumentChunk, on_delete=models.CASCADE, related_name="embedding")
    vector = models.JSONField()
    model = models.CharField(max_length=100, default="text-embedding-3-small")

    class Meta:
        indexes = [
            models.Index(fields=["chunk"]),
        ]


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
