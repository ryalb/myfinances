from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Account,
    Connection,
    FinancialGoal,
    FinancialInstitution,
    NetWorthSnapshot,
    SyncJob,
    Transaction,
)


class FinancialInstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialInstitution
        fields = ("id", "name", "provider_id", "logo_url")


class ConnectionSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = Account
        fields = (
            "id",
            "connection",
            "external_id",
            "name",
            "type",
            "currency",
            "balance",
            "available_balance",
        )


class TransactionSerializer(serializers.ModelSerializer):
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
            "booked_at",
        )


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
    access_token = serializers.CharField()
    expires_at = serializers.CharField(required=False, allow_blank=True)


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
