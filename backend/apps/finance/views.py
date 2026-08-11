import csv
import hmac
import logging
import os
from datetime import date as date_type
from uuid import UUID

from django.conf import settings
from django.db.models import Prefetch, Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .consolidation import (
    build_monthly_cash_flow,
    build_monthly_cash_flow_for_range,
    build_user_financial_summary,
    snapshot_net_worth,
)
from .domain import (
    active_categorization_rules,
    get_or_create_institution,
    normalize_transaction_category,
)
from .filters import filter_transactions, user_transactions
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
    PortfolioReport,
    Subscription,
    SubscriptionPayment,
    SyncJob,
    Transaction,
)
from .pagination import UnboundedCollectionPagination
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
    PortfolioReportSerializer,
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
    throttle_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Login com limite de tentativas.

    O endpoint de token nao tinha throttling nenhum: senha podia ser tentada
    indefinidamente. A taxa vem de DEFAULT_THROTTLE_RATES["login"].
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        # Uso pessoal: desligado por padrao. Ligado, qualquer pessoa com acesso a
        # API cria uma conta. 404 em vez de 403 para nao confirmar o endpoint.
        if not settings.ALLOW_PUBLIC_REGISTRATION:
            logger.warning(
                "Blocked registration attempt (public registration is disabled) from %s",
                request.META.get("REMOTE_ADDR"),
            )
            return Response({"detail": "Not found."}, status=404)

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
            "connection", "connection__identity"
        )


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = UnboundedCollectionPagination

    def get_queryset(self):
        queryset = user_transactions(self.request.user).select_related(
            "account__connection__institution", "card__connection__institution"
        )
        return filter_transactions(queryset, self.request.query_params).order_by("-booked_at")

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        """Categorias presentes nas transações do usuário, para o filtro da tela.

        Vem dos dados e não de um enum: a categoria pode chegar da Pluggy, de uma
        regra do usuário ou das palavras-chave, então um enum fixo ficaria
        desatualizado sem ninguém notar.
        """
        values = (
            user_transactions(request.user)
            .exclude(category="")
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )
        return Response(list(values))


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


class PensionPlanViewSet(viewsets.ModelViewSet):
    """Previdencia privada.

    Escrita existe so para o lancamento manual: a Pluggy cobre Open Finance, e
    PGBL/VGBL fica no Open Insurance (Susep), fora do escopo dela -- entao a
    sincronizacao automatica normalmente nao traz esse dado. `perform_update` e
    `perform_destroy` bloqueiam edicao de planos que vieram sincronizados
    (`connection` preenchido), que devem ser alterados apenas pelo sync.
    """

    serializer_class = PensionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PensionPlan.objects.filter(user=self.request.user).select_related("connection")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, connection=None)

    def perform_update(self, serializer):
        if serializer.instance.connection_id is not None:
            raise PermissionDenied(
                "Planos sincronizados via Open Finance não podem ser editados manualmente."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.connection_id is not None:
            raise PermissionDenied(
                "Planos sincronizados via Open Finance não podem ser excluídos manualmente."
            )
        instance.delete()


class SyncJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = UnboundedCollectionPagination

    def get_queryset(self):
        # `institution` e obrigatorio no select_related: o serializer expoe
        # `connection.institution.name`, entao parar em `connection` faz uma query
        # por job.
        return SyncJob.objects.filter(connection__user=self.request.user).select_related(
            "connection__institution"
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
    # Sem throttling: a Pluggy chega como anonima e trata qualquer resposta fora
    # de 2XX como falha, desistindo apos 9 tentativas. Um 429 perderia eventos.
    # A protecao aqui e o segredo compartilhado, nao a taxa.
    throttle_classes = []

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
        payments = SubscriptionPayment.objects.select_related(
            "matched_transaction", "matched_transaction__account", "matched_transaction__card"
        )
        return (
            Subscription.objects.filter(user=self.request.user)
            .select_related("connection", "payment_account")
            .prefetch_related(Prefetch("payments", queryset=payments))
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubscriptionPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SubscriptionPayment.objects.filter(
            subscription__user=self.request.user
        ).select_related(
            "subscription", "matched_transaction", "matched_transaction__account", "matched_transaction__card"
        )


class CategorizationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = CategorizationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CategorizationRule.objects.filter(user=self.request.user).order_by(
            "priority", "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="reapply")
    def reapply(self, request):
        """Reaplica as regras ao historico ja importado.

        As regras rodavam somente no import, entao criar uma regra nao mexia em
        nada que ja estava no banco -- a tela ficava sem efeito visivel.

        Sincrono de proposito: quem clica quer ver quantos lancamentos mudaram, e
        uma task Celery obrigaria a UI a ficar consultando status. As regras sao
        lidas uma vez e a gravacao e em lote, entao o custo nao cresce por
        transacao.
        """
        rules = active_categorization_rules(request.user)
        queryset = Transaction.objects.filter(
            Q(account__connection__user=request.user) | Q(card__connection__user=request.user)
        ).only("id", "description", "provider_category", "type", "category")

        changed = []
        for transaction in queryset.iterator(chunk_size=2000):
            category = normalize_transaction_category(
                transaction.description,
                transaction.provider_category,
                transaction.type,
                user=request.user,
                rules=rules,
            )
            if category != transaction.category:
                transaction.category = category
                changed.append(transaction)

        if changed:
            Transaction.objects.bulk_update(changed, ["category"], batch_size=1000)

        logger.info(
            "Regras reaplicadas para o usuario %s: %s lancamentos atualizados",
            request.user.pk,
            len(changed),
        )
        return Response({"updated": len(changed)})


class TransactionCSVExportAPIView(APIView):
    """Exporta as transacoes do usuario em CSV.

    Streaming e nao `Response`: o historico nao tem teto e montar o arquivo inteiro
    em memoria antes de responder e o que faz esse tipo de endpoint derrubar o
    processo. Sem paginacao de proposito -- um CSV truncado em 100 linhas de um
    historico de milhares e uma armadilha silenciosa.
    """

    permission_classes = [permissions.IsAuthenticated]

    COLUMNS = (
        "data",
        "descricao",
        "valor",
        "moeda",
        "tipo",
        "categoria",
        "categoria_origem",
        "conta",
        "instituicao",
    )

    TYPE_LABELS = {"credit": "receita", "debit": "despesa"}

    def get(self, request):
        # Mesmos filtros da listagem, via helper compartilhado: um CSV que nao
        # corresponde ao que esta na tela e pior que nao ter exportacao.
        queryset = filter_transactions(
            user_transactions(request.user).select_related(
                "account__connection__institution",
                "card__connection__institution",
            ),
            request.query_params,
        ).order_by("booked_at")

        today = timezone.localdate().isoformat()
        response = StreamingHttpResponse(
            self._rows(queryset), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="transacoes-{today}.csv"'
        return response

    def _rows(self, queryset):
        writer = csv.writer(_PassthroughSink())
        # BOM: sem ele o Excel no Windows le UTF-8 como Latin-1 e "Alimentação"
        # chega quebrado.
        yield "﻿"
        yield writer.writerow(self.COLUMNS)

        for transaction in queryset.iterator(chunk_size=2000):
            holder = transaction.account or transaction.card
            connection = holder.connection if holder else None
            writer_row = (
                transaction.booked_at.date().isoformat(),
                transaction.description,
                # `str(Decimal)` e nao formatacao localizada: LANGUAGE_CODE=pt-br
                # produziria virgula decimal, o que numa coluna CSV vira texto na
                # planilha.
                str(transaction.amount),
                transaction.currency,
                self.TYPE_LABELS.get(transaction.type, transaction.type),
                transaction.category or "",
                transaction.provider_category or "",
                holder.name if holder else "",
                connection.institution.name if connection else "",
            )
            yield writer.writerow(writer_row)


class _PassthroughSink:
    """Sink que devolve o que o csv.writer escreveria.

    `csv.writer` exige um objeto com `write`; para streaming a linha precisa voltar
    ao gerador em vez de ir para um buffer.
    """

    def write(self, value):
        return value


class PortfolioReportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .ai_services import AIServiceUnavailable, LLMService, RAGService

        query = request.data.get("query") or (
            "saude financeira, patrimonio, gastos recorrentes e oportunidades de investimento"
        )

        try:
            # Construidos dentro do try: a checagem de inferencia local levanta no
            # __init__, e isso precisa virar 503 e nao 500.
            rag = RAGService()
            llm = LLMService()

            index_stats = rag.index_user_context(request.user)
            context = rag.retrieve_report_context(request.user, query)
            if not context:
                return Response(
                    {
                        "error": (
                            "Nao ha dados suficientes para gerar o relatorio. "
                            "Conecte uma instituicao e sincronize antes."
                        )
                    },
                    status=422,
                )
            report = llm.generate_portfolio_report(context)
        except AIServiceUnavailable as exc:
            # 503 e nao 500: a causa e a dependencia local (Ollama) estar fora ou o
            # destino de inferencia nao ser permitido, e a mensagem precisa dizer
            # isso em vez de virar stack trace.
            logger.warning("Relatorio de portfolio indisponivel: %s", exc)
            return Response({"error": str(exc)}, status=503)

        # Persistido para referencia futura: sem isto o relatorio so existia no
        # estado do frontend, e um refresh de pagina perdia a analise.
        saved = PortfolioReport.objects.create(
            user=request.user,
            query=query,
            summary=report.get("summary", ""),
            projections=report.get("projections", ""),
            strengths=report.get("strengths", []),
            weaknesses=report.get("weaknesses", []),
            adjustments=report.get("adjustments", []),
            suggestions=report.get("suggestions", []),
            disclaimer=report.get("disclaimer", ""),
            sources=report.get("sources", []),
        )

        data = PortfolioReportSerializer(saved).data
        # `index` e estatistica da indexacao desta chamada, nao do relatorio em si
        # -- fica de fora do modelo persistido para nao gravar um dado que so faz
        # sentido no momento da geracao.
        data["index"] = index_stats
        return Response(data)


class PortfolioReportViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PortfolioReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = UnboundedCollectionPagination

    def get_queryset(self):
        return PortfolioReport.objects.filter(user=self.request.user)
