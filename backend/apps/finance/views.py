import hmac
import logging
import os
from datetime import date as date_type
from uuid import UUID

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
from .domain import get_or_create_institution
from .models import (
    Account,
    Card,
    CategorizationRule,
    Connection,
    ConnectionStatus,
    FinancialGoal,
    FinancialInstitution,
    Investment,
    InvestmentPosition,
    NetWorthSnapshot,
    PensionPlan,
    Subscription,
    SubscriptionPayment,
    SyncJob,
    Transaction,
)
from .serializers import (
    AccountSerializer,
    CardSerializer,
    CategorizationRuleSerializer,
    ConnectionSerializer,
    FinancialGoalSerializer,
    FinancialInstitutionSerializer,
    FinancialSummarySerializer,
    InvestmentPositionSerializer,
    InvestmentSerializer,
    MonthlyCashFlowSerializer,
    PensionPlanSerializer,
    RegisterSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionSerializer,
    SyncJobSerializer,
    TransactionSerializer,
)
from .services import PluggyClient
from .tasks import recompute_user_snapshot, sync_connection_data

logger = logging.getLogger(__name__)


class HealthCheckAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class CurrentUserAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        )


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
        return Account.objects.filter(connection__user=self.request.user).select_related(
            "connection"
        )


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


class CardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Card.objects.filter(connection__user=self.request.user).select_related("connection")


class InvestmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvestmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Investment.objects.filter(connection__user=self.request.user).select_related(
            "connection"
        )


class InvestmentPositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvestmentPositionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return InvestmentPosition.objects.filter(
            investment__connection__user=self.request.user
        ).select_related("investment")


class PensionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PensionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PensionPlan.objects.filter(connection__user=self.request.user).select_related(
            "connection"
        )


class SyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SyncJob.objects.filter(connection__user=self.request.user).select_related(
            "connection"
        )


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

        if year_raw and month_raw:
            year = int(year_raw)
            month = int(month_raw)
            cash_flow = build_monthly_cash_flow(request.user, year=year, month=month)
            serializer = MonthlyCashFlowSerializer(cash_flow)
            return Response(serializer.data)

        results = []
        ref_year = today.year
        ref_month = today.month
        for i in range(11, -1, -1):
            month_offset = ref_month - i
            year_offset = ref_year
            while month_offset <= 0:
                month_offset += 12
                year_offset -= 1
            while month_offset > 12:
                month_offset -= 12
                year_offset += 1

            start = date_type(year_offset, month_offset, 1)
            if month_offset == 12:
                end = date_type(year_offset + 1, 1, 1)
            else:
                end = date_type(year_offset, month_offset + 1, 1)

            flow = build_monthly_cash_flow_for_range(request.user, start, end)
            results.append(
                {
                    "year": year_offset,
                    "month": month_offset,
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
        return Response(
            {
                "error": (
                    "Fluxo de conexão direta desativado. "
                    "Para uso pessoal gratuito, utilize o Meu Pluggy: "
                    "1) cadastre-se em meu.pluggy.ai e conecte suas contas; "
                    "2) no Dashboard da Pluggy, use Conectar Conta → MeuPluggy e "
                    "autorize uma conexão por vez (a tela de consentimento aceita "
                    "apenas uma); "
                    "3) envie cada itemId para POST /api/v1/pluggy/items/."
                )
            },
            status=400,
        )


class PluggyRegenerateAuthAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        client = PluggyClient()
        try:
            client._invalidate_api_key()
            client._get_api_key()
            logger.info("Pluggy auth regenerated by user=%s", request.user.id)
            return Response(
                {
                    "status": "ok",
                    "message": "Autenticação do Pluggy revalidada com sucesso.",
                }
            )
        except Exception as exc:
            logger.error("Pluggy regenerate auth failed: %s", exc)
            return Response({"status": "error", "message": str(exc)}, status=400)


class PluggyWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    ALLOWED_EVENTS = {
        "item/created",
        "item/updated",
        "item/error",
        "item/waiting_user_input",
        "item/login_succeeded",
        "item/deleted",
        "transactions/created",
        "transactions/updated",
        "transactions/deleted",
    }

    def post(self, request):
        expected = os.getenv("PLUGGY_WEBHOOK_SECRET", "")
        if not expected:
            logger.error("PLUGGY_WEBHOOK_SECRET is not configured; refusing to process webhooks.")
            return Response({"detail": "Webhook not configured."}, status=503)

        provided = request.query_params.get("token", "")
        if not hmac.compare_digest(provided, expected):
            logger.warning(
                "Pluggy webhook rejected: invalid token (remote=%s)",
                request.META.get("REMOTE_ADDR"),
            )
            return Response({"detail": "Forbidden."}, status=403)

        event = request.data.get("event", "")
        item_id = request.data.get("itemId")
        client_user_id = request.data.get("clientUserId")

        logger.info(
            "Pluggy webhook event=%s item_id=%s client_user_id=%s payload_keys=%s",
            event,
            item_id,
            client_user_id,
            sorted(request.data.keys()),
        )

        if not item_id or event not in self.ALLOWED_EVENTS:
            return Response({"status": "ignored"})

        from .tasks import process_pluggy_webhook

        process_pluggy_webhook.delay(event, item_id, client_user_id, dict(request.data))
        return Response({"status": "queued"})


class PluggyImportItemAPIView(APIView):
    """Importa um item da Pluggy pelo seu itemId.

    Substitui o antigo /pluggy/discover/, que dependia de `GET /items` --
    endpoint que a Pluggy nao expoe (responde 401). O itemId vem do Dashboard
    da Pluggy (Itens Conectados) ou do payload do webhook.

    Cada conexao do Meu Pluggy e um item separado: a tela de consentimento
    permite escolher uma conexao por autorizacao.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        item_id = str(request.data.get("itemId") or "").strip()
        if not item_id:
            return Response(
                {
                    "error": (
                        "Informe o itemId. Ele aparece no Dashboard da Pluggy, "
                        "em Itens Conectados, acima do nome do conector."
                    )
                },
                status=400,
            )

        try:
            UUID(item_id)
        except ValueError:
            return Response({"error": "itemId invalido: esperado um UUID."}, status=400)

        existing = Connection.objects.filter(external_id=item_id).first()
        if existing and existing.user_id != request.user.id:
            logger.warning(
                "User %s tried to import item %s owned by user %s",
                request.user.id,
                item_id,
                existing.user_id,
            )
            return Response({"error": "Este item ja esta vinculado a outra conta."}, status=409)

        client = PluggyClient(force_production=True)
        try:
            item_data = client.fetch_item(item_id)
        except Exception as exc:
            logger.warning("Pluggy import: fetch_item(%s) failed: %s", item_id, exc)
            return Response(
                {
                    "error": (
                        "Nao foi possivel consultar este item na Pluggy. "
                        "Confira o itemId e se ele pertence a esta aplicacao."
                    )
                },
                status=502,
            )

        status_value = item_data.get("status", "")
        institution = get_or_create_institution(item_data)

        connection, created = Connection.objects.get_or_create(
            external_id=item_id,
            defaults={
                "user": request.user,
                "institution": institution,
                "status": (
                    ConnectionStatus.ACTIVE
                    if status_value == "UPDATED"
                    else ConnectionStatus.PENDING
                ),
            },
        )

        sync_job = SyncJob.objects.create(connection=connection, kind="full")
        sync_connection_data.delay(sync_job.id)

        logger.info(
            "Pluggy item %s imported by user=%s (created=%s status=%s)",
            item_id,
            request.user.id,
            created,
            status_value,
        )

        return Response(
            {
                "id": connection.id,
                "external_id": connection.external_id,
                "status": connection.status,
                "created": created,
                "item_status": status_value,
                "sync_job_id": sync_job.id,
                "message": (
                    "Item importado. A sincronizacao foi enfileirada."
                    if status_value == "UPDATED"
                    else f"Item importado com status {status_value}; "
                    "a sincronizacao pode vir vazia ou parcial."
                ),
            },
            status=201 if created else 200,
        )


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related(
            "connection", "payment_account"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubscriptionPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SubscriptionPayment.objects.filter(
            subscription__user=self.request.user
        ).select_related("subscription")


class CategorizationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = CategorizationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CategorizationRule.objects.filter(user=self.request.user).order_by(
            "priority", "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PortfolioReportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .ai_services import LLMService, RAGService

        rag = RAGService()
        llm = LLMService()

        rag.index_user_context(request.user)
        chunks = rag.search(request.user, "relatório financeiro personalizado", top_k=5)
        report = llm.generate_portfolio_report(request.user, chunks)
        return Response(report)
