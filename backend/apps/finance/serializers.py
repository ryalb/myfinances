from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Account,
    Card,
    CategorizationRule,
    Connection,
    FinancialGoal,
    FinancialInstitution,
    FutureProjectionReport,
    Identity,
    Investment,
    InvestmentPosition,
    MonthlyReview,
    NetWorthSnapshot,
    PensionPlan,
    PortfolioReport,
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
        )

    def get_identity(self, obj):
        identity = getattr(obj.connection, "identity", None)
        return IdentitySerializer(identity).data if identity else None


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
    class Meta:
        model = Investment
        fields = (
            "id",
            "connection",
            "external_id",
            "name",
            "kind",
            "currency",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


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
