from django.contrib import admin
from django.urls import include, path
from graphene_django.views import GraphQLView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.finance.views import (
    AccountViewSet,
    ConnectionViewSet,
    FinancialGoalViewSet,
    FinancialInstitutionViewSet,
    FinancialSummaryAPIView,
    HealthCheckAPIView,
    MonthlyCashFlowAPIView,
    NetWorthSnapshotAPIView,
    PluggyConnectTokenAPIView,
    RegisterAPIView,
    SyncJobViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
router.register(r"institutions", FinancialInstitutionViewSet, basename="institution")
router.register(r"connections", ConnectionViewSet, basename="connection")
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"transactions", TransactionViewSet, basename="transaction")
router.register(r"sync-jobs", SyncJobViewSet, basename="sync-job")
router.register(r"goals", FinancialGoalViewSet, basename="goal")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthCheckAPIView.as_view(), name="health"),
    path("api/v1/", include(router.urls)),
    path("api/v1/auth/register/", RegisterAPIView.as_view(), name="register"),
    path("api/v1/summary/", FinancialSummaryAPIView.as_view(), name="financial-summary"),
    path("api/v1/cash-flow/", MonthlyCashFlowAPIView.as_view(), name="monthly-cash-flow"),
    path(
        "api/v1/net-worth/snapshot/",
        NetWorthSnapshotAPIView.as_view(),
        name="net-worth-snapshot",
    ),
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path(
        "api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    path(
        "api/v1/pluggy/connect-token/",
        PluggyConnectTokenAPIView.as_view(),
        name="pluggy-connect-token",
    ),
    path("graphql/", GraphQLView.as_view(graphiql=True)),
]
