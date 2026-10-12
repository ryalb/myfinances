from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.finance.graphql_view import JWTGraphQLView
from apps.finance.views import (
    AccountViewSet,
    BudgetBucketTargetsAPIView,
    CardViewSet,
    CategorizationRuleViewSet,
    ChatAPIView,
    ConnectionViewSet,
    CurrentUserAPIView,
    ExecutiveReportAPIView,
    FinanceTagViewSet,
    FinancialGoalViewSet,
    FinancialInstitutionViewSet,
    FinancialSummaryAPIView,
    FutureProjectionAPIView,
    HealthCheckAPIView,
    InvestmentPositionViewSet,
    InvestmentViewSet,
    MarketBenchmarksAPIView,
    MonthlyCashFlowAPIView,
    MonthlyReviewAPIView,
    NetWorthSnapshotAPIView,
    PensionPlanViewSet,
    PluggyConnectTokenAPIView,
    PluggyImportItemAPIView,
    PluggyRegenerateAuthAPIView,
    PluggyWebhookAPIView,
    PortfolioBuilderAPIView,
    PortfolioReportAPIView,
    PortfolioRiskAPIView,
    PortfolioTargetsAPIView,
    RegisterAPIView,
    SubscriptionPaymentViewSet,
    SubscriptionViewSet,
    SyncJobViewSet,
    ThrottledTokenObtainPairView,
    TransactionCSVExportAPIView,
    TransactionViewSet,
)

router = DefaultRouter()
router.register(r"institutions", FinancialInstitutionViewSet, basename="institution")
router.register(r"connections", ConnectionViewSet, basename="connection")
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"transactions", TransactionViewSet, basename="transaction")
router.register(r"cards", CardViewSet, basename="card")
router.register(r"investments", InvestmentViewSet, basename="investment")
router.register(r"investment-positions", InvestmentPositionViewSet, basename="investment-position")
router.register(r"pension-plans", PensionPlanViewSet, basename="pension-plan")
router.register(r"sync-jobs", SyncJobViewSet, basename="sync-job")
router.register(r"goals", FinancialGoalViewSet, basename="goal")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(
    r"subscription-payments", SubscriptionPaymentViewSet, basename="subscription-payment"
)
router.register(r"categorization-rules", CategorizationRuleViewSet, basename="categorization-rule")
router.register(r"finance-tags", FinanceTagViewSet, basename="finance-tag")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthCheckAPIView.as_view(), name="health"),
    path("api/v1/auth/me/", CurrentUserAPIView.as_view(), name="current-user"),
    path("api/v1/", include(router.urls)),
    path("api/v1/auth/register/", RegisterAPIView.as_view(), name="register"),
    path("api/v1/summary/", FinancialSummaryAPIView.as_view(), name="financial-summary"),
    path("api/v1/cash-flow/", MonthlyCashFlowAPIView.as_view(), name="monthly-cash-flow"),
    path(
        "api/v1/monthly-review/",
        MonthlyReviewAPIView.as_view(),
        name="monthly-review",
    ),
    path(
        "api/v1/portfolio-targets/",
        PortfolioTargetsAPIView.as_view(),
        name="portfolio-targets",
    ),
    path(
        "api/v1/market-benchmarks/",
        MarketBenchmarksAPIView.as_view(),
        name="market-benchmarks",
    ),
    path(
        "api/v1/portfolio-risk/",
        PortfolioRiskAPIView.as_view(),
        name="portfolio-risk",
    ),
    path(
        "api/v1/budget-bucket-targets/",
        BudgetBucketTargetsAPIView.as_view(),
        name="budget-bucket-targets",
    ),
    path(
        "api/v1/net-worth/snapshot/",
        NetWorthSnapshotAPIView.as_view(),
        name="net-worth-snapshot",
    ),
    path(
        "api/v1/auth/token/",
        ThrottledTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "api/v1/pluggy/connect-token/",
        PluggyConnectTokenAPIView.as_view(),
        name="pluggy-connect-token",
    ),
    path(
        "api/v1/pluggy/webhook/",
        PluggyWebhookAPIView.as_view(),
        name="pluggy-webhook",
    ),
    path(
        "api/v1/pluggy/items/",
        PluggyImportItemAPIView.as_view(),
        name="pluggy-import-item",
    ),
    path(
        "api/v1/pluggy/regenerate-auth/",
        PluggyRegenerateAuthAPIView.as_view(),
        name="pluggy-regenerate-auth",
    ),
    path(
        "api/v1/export/transactions.csv",
        TransactionCSVExportAPIView.as_view(),
        name="export-transactions-csv",
    ),
    path(
        "api/v1/ai/portfolio-report/",
        PortfolioReportAPIView.as_view(),
        name="portfolio-report",
    ),
    path(
        "api/v1/ai/future-projection/",
        FutureProjectionAPIView.as_view(),
        name="future-projection-report",
    ),
    path(
        "api/v1/ai/portfolio-builder/",
        PortfolioBuilderAPIView.as_view(),
        name="portfolio-builder-report",
    ),
    path(
        "api/v1/ai/executive-report/",
        ExecutiveReportAPIView.as_view(),
        name="executive-report",
    ),
    path(
        "api/v1/ai/chat/",
        ChatAPIView.as_view(),
        name="ai-chat",
    ),
    path("graphql/", JWTGraphQLView.as_view(graphiql=True)),
]
