from datetime import date as date_type
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .consolidation import (
    build_monthly_cash_flow,
    build_monthly_cash_flow_for_range,
    build_user_financial_summary,
    snapshot_net_worth,
)
from .models import (
    Account,
    Connection,
    FinancialGoal,
    FinancialInstitution,
    NetWorthSnapshot,
    SyncJob,
    Transaction,
)
from .serializers import (
    AccountSerializer,
    ConnectionSerializer,
    FinancialGoalSerializer,
    FinancialInstitutionSerializer,
    FinancialSummarySerializer,
    MonthlyCashFlowSerializer,
    PluggyConnectTokenRequestSerializer,
    PluggyConnectTokenResponseSerializer,
    RegisterSerializer,
    SyncJobSerializer,
    TransactionSerializer,
)
from .services import PluggyClient
from .tasks import recompute_user_snapshot, sync_connection_data


class HealthCheckAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"id": user.id, "email": user.email})


class FinancialInstitutionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FinancialInstitution.objects.all().order_by("name")
    serializer_class = FinancialInstitutionSerializer
    permission_classes = [permissions.IsAuthenticated]


class ConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = ConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Connection.objects.filter(user=self.request.user).select_related("institution")

    def perform_create(self, serializer):
        connection = serializer.save(user=self.request.user)
        sync_job = SyncJob.objects.create(connection=connection, kind="full")
        sync_connection_data.delay(sync_job.id)

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):
        connection = self.get_object()
        kind = request.data.get("kind", "incremental")
        sync_job = SyncJob.objects.create(connection=connection, kind=kind)
        sync_connection_data.delay(sync_job.id)
        return Response(SyncJobSerializer(sync_job).data)


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Account.objects.filter(
            connection__user=self.request.user
        ).select_related("connection")


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Transaction.objects.filter(
            Q(account__connection__user=self.request.user)
            | Q(card__connection__user=self.request.user)
        ).select_related("account", "card")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(booked_at__gte=start_date)
        if end_date:
            qs = qs.filter(booked_at__lt=end_date)
        return qs


class SyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SyncJob.objects.filter(
            connection__user=self.request.user
        ).select_related("connection")


class FinancialSummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        summary = build_user_financial_summary(request.user)
        serializer = FinancialSummarySerializer(summary)
        return Response(serializer.data)


class MonthlyCashFlowAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        year_raw, month_raw = request.query_params.get("year"), request.query_params.get("month")

        # If year+month provided, return single month; otherwise return 12-month history
        if year_raw and month_raw:
            year = int(year_raw)
            month = int(month_raw)
            cash_flow = build_monthly_cash_flow(request.user, year=year, month=month)
            serializer = MonthlyCashFlowSerializer(cash_flow)
            return Response(serializer.data)

        # Return last 12 months of cash flow
        results = []
        for i in range(11, -1, -1):
            ref_date = today - timedelta(days=30 * i)
            if ref_date.month == 1:
                start = date_type(ref_date.year - 1, 12, 1)
                end = date_type(ref_date.year, 1, 1)
            else:
                start = date_type(ref_date.year, ref_date.month - 1, 1)
                end = date_type(ref_date.year, ref_date.month, 1)

            flow = build_monthly_cash_flow_for_range(request.user, start, end)
            results.append(
                {
                    "year": ref_date.year,
                    "month": ref_date.month,
                    "income": float(flow["income"]),
                    "expenses": float(flow["expenses"]),
                    "savings": float(flow["savings"]),
                    "savings_rate": float(flow["savings_rate"]),
                }
            )
        return Response(results)


class NetWorthSnapshotAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        snapshots = NetWorthSnapshot.objects.filter(user=request.user).order_by("date")[:30]

        data = []
        for s in snapshots:
            data.append(
                {
                    "id": s.id,
                    "date": s.date.isoformat(),
                    "assets": str(s.assets),
                    "liabilities": str(s.liabilities),
                    "net_worth": str(s.net_worth),
                }
            )
        return Response(data)

    def post(self, request):
        snapshot = snapshot_net_worth(request.user)
        return Response(
            {
                "id": snapshot.id,
                "date": snapshot.date.isoformat(),
                "assets": str(snapshot.assets),
                "liabilities": str(snapshot.liabilities),
                "net_worth": str(snapshot.net_worth),
            }
        )

    def put(self, request):
        recompute_user_snapshot.delay(request.user.id)
        return Response({"status": "queued"})


class FinancialGoalViewSet(viewsets.ModelViewSet):
    serializer_class = FinancialGoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FinancialGoal.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PluggyConnectTokenAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PluggyConnectTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = PluggyClient()
        payload = {
            "clientUserId": serializer.validated_data.get("client_user_id", str(request.user.id)),
        }
        if "institution_id" in serializer.validated_data:
            payload["institutionId"] = serializer.validated_data["institution_id"]
        token_data = client.create_connect_token(payload)
        response_serializer = PluggyConnectTokenResponseSerializer(token_data)
        return Response(response_serializer.data)
