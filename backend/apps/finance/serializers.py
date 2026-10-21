from django.contrib.auth import get_user_model
from rest_framework import serializers

from .investment_categories import classify_display_category
from .models import (
    Account,
    AssetClass,
    BudgetBucket,
    BudgetBucketTarget,
    Card,
    CategorizationRule,
    ChatMessage,
    Connection,
    ExecutiveReport,
    FinanceTag,
    FinancialGoal,
    FinancialInstitution,
    FutureProjectionReport,
    Identity,
    Investment,
    InvestmentPosition,
    MonthlyReview,
    NetWorthSnapshot,
    PensionPlan,
    PortfolioBuilderReport,
    PortfolioReport,
    PortfolioTarget,
    Subscription,
    SubscriptionPayment,
    SyncJob,
    Transaction,
)


class FinancialInstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialInstitution
        fields = ("id", "name", "provider_id", "logo_url")


class IdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Identity
        fields = (
            "id",
            "full_name",
            "document",
            "document_type",
            "birth_date",
            "job_title",
            "email",
            "phone_number",
            "address",
        )


class ConnectionSerializer(serializers.ModelSerializer):
    institution = FinancialInstitutionSerializer(read_only=True)

    class Meta:
        model = Connection
        fields = (
            "id",
            "institution",
            "external_id",
            "status",
            "last_synced_at",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "last_synced_at", "error_message", "created_at", "updated_at")


class AccountSerializer(serializers.ModelSerializer):
    identity = serializers.SerializerMethodField()
    # Fallback de nome na tela: alguns bancos mandam `name` generico ("Conta
    # Corrente", igual ao label do `type`) para toda conta do mesmo tipo, sem
    # apelido proprio -- mesmo campo que `TransactionSerializer.institution_name`
    # ja resolve para o extrato, aqui pra tela de contas distinguir contas do
    # mesmo tipo em instituicoes diferentes.
    institution_name = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = (
            "id",
            "connection",
            "external_id",
            "name",
            "number",
            "type",
            "currency",
            "balance",
            "available_balance",
            "identity",
            "institution_name",
        )

    def get_identity(self, obj):
        identity = getattr(obj.connection, "identity", None)
        return IdentitySerializer(identity).data if identity else None

    def get_institution_name(self, obj):
        return obj.connection.institution.name


class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    institution_name = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = (
            "id",
            "account",
            "card",
            "external_id",
            "description",
            "amount",
            "currency",
            "type",
            "category",
            "category_is_manual",
            "suggested_category",
            "suggested_category_confidence",
            "provider_category",
            "is_internal_transfer",
            "booked_at",
            "account_name",
            "institution_name",
        )

    def get_account_name(self, obj):
        holder = obj.account or obj.card
        return holder.name if holder else ""

    def get_institution_name(self, obj):
        holder = obj.account or obj.card
        connection = holder.connection if holder else None
        return connection.institution.name if connection else ""


class TransactionCategoryInputSerializer(serializers.Serializer):
    """Corpo do PATCH de `/transactions/{id}/category/` -- edicao manual."""

    category = serializers.CharField(max_length=100)

    def validate_category(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Categoria não pode ser vazia.")
        return value


class NetWorthSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetWorthSnapshot
        fields = ("id", "date", "assets", "liabilities", "net_worth")


class SyncJobSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="connection.institution.name", read_only=True)

    class Meta:
        model = SyncJob
        fields = (
            "id",
            "connection",
            "institution_name",
            "kind",
            "status",
            "started_at",
            "finished_at",
            "error_message",
            "created_at",
        )


class PortfolioReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioReport
        fields = (
            "id",
            "query",
            "summary",
            "projections",
            "strengths",
            "weaknesses",
            "adjustments",
            "suggestions",
            "disclaimer",
            "sources",
            "created_at",
        )
        read_only_fields = fields


class FutureProjectionReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = FutureProjectionReport
        fields = (
            "id",
            "projection",
            "narrative",
            "leverage_explanation",
            "goal_commentary",
            "disclaimer",
            "sources",
            "created_at",
        )
        read_only_fields = fields


class PortfolioTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioTarget
        fields = ("id", "asset_class", "target_percentage", "created_at", "updated_at")
        read_only_fields = fields


class PortfolioTargetInputSerializer(serializers.Serializer):
    """Uma linha do PUT em lote de `/api/v1/portfolio-targets/`.

    So valida a forma de cada linha -- a soma das linhas (~100%) e checada pela
    view sobre o lote inteiro, nao aqui: uma unica linha nunca soma 100% sozinha.
    """

    asset_class = serializers.ChoiceField(choices=AssetClass.choices)
    target_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100
    )


class BudgetBucketTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetBucketTarget
        fields = ("id", "bucket", "target_percentage", "created_at", "updated_at")
        read_only_fields = fields


class BudgetBucketTargetInputSerializer(serializers.Serializer):
    """Uma linha do PUT em lote de `/api/v1/budget-bucket-targets/` -- mesmo
    papel de `PortfolioTargetInputSerializer`, taxonomia do otimizador."""

    bucket = serializers.ChoiceField(choices=BudgetBucket.choices)
    target_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100
    )


class FinancialSummarySerializer(serializers.Serializer):
    assets = serializers.DecimalField(max_digits=16, decimal_places=2)
    liabilities = serializers.DecimalField(max_digits=16, decimal_places=2)
    net_worth = serializers.DecimalField(max_digits=16, decimal_places=2)
    breakdown = serializers.DictField(
        child=serializers.DecimalField(max_digits=16, decimal_places=2)
    )


class MonthlyCashFlowSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    income = serializers.DecimalField(max_digits=16, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=16, decimal_places=2)
    savings = serializers.DecimalField(max_digits=16, decimal_places=2)
    savings_rate = serializers.DecimalField(max_digits=10, decimal_places=2)


class PortfolioConcentrationRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)


class PortfolioCurrencyExposureSerializer(serializers.Serializer):
    brl_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    brl_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    foreign_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    foreign_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    by_currency = PortfolioConcentrationRowSerializer(many=True)


class PortfolioRiskSerializer(serializers.Serializer):
    issuer_concentration = PortfolioConcentrationRowSerializer(many=True)
    indexer_concentration = PortfolioConcentrationRowSerializer(many=True)
    currency_exposure = PortfolioCurrencyExposureSerializer()


class CdiBenchmarkSerializer(serializers.Serializer):
    as_of = serializers.DateField(allow_null=True)
    annual_rate = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)
    m1 = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)
    m3 = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)
    m12 = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)


class IpcaBenchmarkSerializer(serializers.Serializer):
    as_of = serializers.DateField(allow_null=True)
    m1 = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)
    m3 = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)
    m12 = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)


class CdiSinceSerializer(serializers.Serializer):
    date = serializers.DateField()
    value = serializers.DecimalField(max_digits=10, decimal_places=4, allow_null=True)


class MarketBenchmarksSerializer(serializers.Serializer):
    cdi = CdiBenchmarkSerializer()
    ipca = IpcaBenchmarkSerializer()
    cdi_since = CdiSinceSerializer(many=True)


class CategoryTotalSerializer(serializers.Serializer):
    category = serializers.CharField()
    total = serializers.DecimalField(max_digits=16, decimal_places=2)
    count = serializers.IntegerField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)


class TransactionStatsSerializer(serializers.Serializer):
    total_income = serializers.DecimalField(max_digits=16, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=16, decimal_places=2)
    balance = serializers.DecimalField(max_digits=16, decimal_places=2)
    transaction_count = serializers.IntegerField()
    average_expense = serializers.DecimalField(max_digits=16, decimal_places=2)
    expense_categories = CategoryTotalSerializer(many=True)
    income_categories = CategoryTotalSerializer(many=True)


class MonthlyReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyReview
        fields = ("id", "year", "month", "adjustments", "completed_at", "created_at", "updated_at")
        read_only_fields = ("id", "year", "month", "created_at", "updated_at")


class CategoryDeltaSerializer(serializers.Serializer):
    category = serializers.CharField()
    current_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    previous_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    delta = serializers.DecimalField(max_digits=16, decimal_places=2)


class MonthlyReviewSummarySerializer(serializers.Serializer):
    review = MonthlyReviewSerializer()
    net_worth_delta = serializers.DecimalField(
        max_digits=16, decimal_places=2, allow_null=True
    )
    current_net_worth = serializers.DecimalField(
        max_digits=16, decimal_places=2, allow_null=True
    )
    savings_rate_trend = MonthlyCashFlowSerializer(many=True)
    category_deltas = CategoryDeltaSerializer(many=True)
    achievements = serializers.ListField(child=serializers.CharField())


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        user_model = get_user_model()
        return user_model.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

    def validate_email(self, value):
        user_model = get_user_model()
        if user_model.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email já cadastrado.")
        return value


class PluggyConnectTokenRequestSerializer(serializers.Serializer):
    institution_id = serializers.IntegerField(required=False)
    client_user_id = serializers.CharField(required=False, allow_blank=True)


class PluggyConnectTokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField(source="accessToken")
    expires_in = serializers.CharField(required=False, allow_blank=True, source="expiresIn")


class FinancialGoalSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = FinancialGoal
        fields = (
            "id",
            "name",
            "target_amount",
            "current_amount",
            "target_date",
            "status",
            "progress_percentage",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_progress_percentage(self, obj):
        if obj.target_amount and obj.target_amount > 0:
            return float((obj.current_amount / obj.target_amount) * 100)
        return 0.0


class UserScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """FK que so aceita objetos do proprio usuario autenticado.

    O `ModelSerializer` monta a FK validando contra a tabela inteira: qualquer id
    existente passa. Como `SubscriptionPayment.subscription`,
    `Subscription.connection` e `Subscription.payment_account` sao gravaveis, isso
    permitia a um usuario autenticado pendurar a propria assinatura na conta
    bancaria de outro -- ou criar pagamentos dentro da assinatura de outro.

    `user_path` e o lookup do dono a partir do modelo relacionado (`user` para
    Subscription/Connection, `connection__user` para Account).
    """

    def __init__(self, *args, user_path: str, **kwargs):
        self.user_path = user_path
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.context.get("request"), "user", None)
        # Falha fechada: sem request autenticado no contexto nenhum id e valido.
        if user is None or not user.is_authenticated:
            return queryset.none()
        return queryset.filter(**{self.user_path: user})


class FinanceTagSerializer(serializers.ModelSerializer):
    account = UserScopedPrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        user_path="connection__user",
        required=False,
        allow_null=True,
    )
    investment = UserScopedPrimaryKeyRelatedField(
        queryset=Investment.objects.all(),
        user_path="connection__user",
        required=False,
        allow_null=True,
    )
    goal = UserScopedPrimaryKeyRelatedField(
        queryset=FinancialGoal.objects.all(), user_path="user", required=False, allow_null=True
    )

    class Meta:
        model = FinanceTag
        fields = (
            "id",
            "kind",
            "value",
            "account",
            "investment",
            "goal",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        # DRF gera um `UniqueTogetherValidator` por `UniqueConstraint` do model,
        # inclusive as tres condicionais (`unique_tag_per_*_and_kind`) -- e
        # `enforce_required_fields` desse validador forca como obrigatorios os
        # `condition_fields` (account/investment/goal), contradizendo a propria
        # regra do model de que exatamente um dos tres deve vir preenchido.
        # Sem este `validators = []` toda criacao via API falhava com "este
        # campo e obrigatorio" no primeiro dos dois campos nao usados. A
        # checagem de duplicidade correta fica em `validate()` abaixo.
        validators = []

    def validate(self, attrs):
        targets = {field: attrs.get(field) for field in ("account", "investment", "goal")}
        filled = {field: value for field, value in targets.items() if value is not None}
        if len(filled) != 1:
            raise serializers.ValidationError(
                "Informe exatamente um de: account, investment, goal."
            )

        field_name, target = next(iter(filled.items()))
        duplicates = FinanceTag.objects.filter(kind=attrs.get("kind"), **{field_name: target})
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {field_name: "Já existe uma tag deste tipo para este alvo."}
            )
        return attrs


class PortfolioBuilderReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioBuilderReport
        fields = (
            "id",
            "drift",
            "guidance",
            "rebalancing_actions",
            "common_mistakes",
            "disclaimer",
            "sources",
            "created_at",
        )
        read_only_fields = fields


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ("id", "role", "content", "sources", "created_at")
        read_only_fields = fields


class ExecutiveReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutiveReport
        fields = (
            "id",
            "contribution_amount",
            "contribution_plan",
            "summary",
            "goal_fit",
            "performance_verdict",
            "contribution_rationale",
            "disclaimer",
            "sources",
            "created_at",
        )
        read_only_fields = fields


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    subscription = UserScopedPrimaryKeyRelatedField(
        queryset=Subscription.objects.all(), user_path="user"
    )
    matched_transaction = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPayment
        fields = (
            "id",
            "subscription",
            "due_date",
            "paid_date",
            "status",
            "paid_amount",
            "matched_transaction",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_matched_transaction(self, obj):
        tx = obj.matched_transaction
        if not tx:
            return None
        return {
            "id": tx.id,
            "description": tx.description,
            "amount": tx.amount,
            "booked_at": tx.booked_at,
            "account_name": tx.account.name if tx.account else (tx.card.name if tx.card else None),
        }


class SubscriptionSerializer(serializers.ModelSerializer):
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)
    connection = UserScopedPrimaryKeyRelatedField(
        queryset=Connection.objects.all(),
        user_path="user",
        required=False,
        allow_null=True,
    )
    payment_account = UserScopedPrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        user_path="connection__user",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Subscription
        fields = (
            "id",
            "connection",
            "name",
            "category",
            "amount",
            "due_day",
            "payment_account",
            "is_active",
            "payments",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class CategorizationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorizationRule
        fields = (
            "id",
            "pattern",
            "category",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = (
            "id",
            "connection",
            "external_id",
            "name",
            "last4",
            "credit_limit",
            "current_balance",
            "due_day",
            "close_day",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class InvestmentSerializer(serializers.ModelSerializer):
    # Categoria de exibicao (Renda Fixa/Acoes/FII/...), derivada de kind+code --
    # ver investment_categories.py. Separada de `AssetClass`/FinanceTag, que e a
    # taxonomia das metas do Portfolio Builder.
    display_category = serializers.SerializerMethodField()
    display_category_label = serializers.SerializerMethodField()
    display_category_estimated = serializers.SerializerMethodField()

    class Meta:
        model = Investment
        fields = (
            "id",
            "connection",
            "external_id",
            "name",
            "kind",
            "currency",
            "subtype",
            "code",
            "isin",
            "issuer",
            "issue_date",
            "due_date",
            "rate_type",
            "tax_exempt",
            "rate_periodicity",
            "indexer_additional_info",
            "display_category",
            "display_category_label",
            "display_category_estimated",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
            "display_category",
            "display_category_label",
            "display_category_estimated",
        )

    def get_display_category(self, obj):
        return classify_display_category(obj).key

    def get_display_category_label(self, obj):
        return classify_display_category(obj).label

    def get_display_category_estimated(self, obj):
        return classify_display_category(obj).estimated


class InvestmentPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentPosition
        fields = (
            "id",
            "investment",
            "as_of_date",
            "quantity",
            "unit_price",
            "market_value",
            "last_month_rate",
            "last_twelve_months_rate",
            "annual_rate",
            "fixed_annual_rate",
            "rate",
            "amount_profit",
            "amount_original",
            "estimated_amount_original",
            "status",
            "purchase_date",
            "grace_period_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class PensionPlanSerializer(serializers.ModelSerializer):
    is_manual = serializers.SerializerMethodField()

    class Meta:
        model = PensionPlan
        fields = (
            "id",
            "name",
            "provider",
            "balance",
            "is_manual",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_is_manual(self, obj):
        return obj.connection_id is None
