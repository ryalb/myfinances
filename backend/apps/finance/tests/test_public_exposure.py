"""Testes das protecoes de exposicao publica.

O tunel do ngrok encaminha a porta inteira, nao um path. Sem restricao, expor o
webhook da Pluggy expunha /admin/, /graphql/, o endpoint de token e o registro
publico -- com traceback completo se DEBUG=True.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

TUNNEL_HOST = "platonic-groin-basin.ngrok-free.dev"
WEBHOOK = "/api/v1/pluggy/webhook/"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def tunnel(settings):
    settings.PUBLIC_TUNNEL_HOSTS = [TUNNEL_HOST]
    settings.ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", TUNNEL_HOST]
    return TUNNEL_HOST


class TestPublicTunnelRestriction:
    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "path",
        [
            "/admin/",
            "/graphql/",
            "/api/v1/auth/token/",
            "/api/v1/auth/register/",
            "/api/v1/auth/me/",
            "/api/v1/pluggy/items/",
            "/api/v1/pluggy/regenerate-auth/",
            "/api/v1/summary/",
            "/api/v1/connections/",
            "/api/v1/transactions/",
        ],
    )
    def test_tunnel_host_cannot_reach_anything_but_the_webhook(self, api, tunnel, path):
        response = api.get(path, HTTP_HOST=tunnel)
        assert response.status_code == 404, f"{path} acessivel pelo tunel"

    @pytest.mark.django_db
    def test_tunnel_host_reaches_the_webhook(self, api, tunnel, monkeypatch):
        monkeypatch.setenv("PLUGGY_WEBHOOK_SECRET", "segredo")
        response = api.post(
            f"{WEBHOOK}?token=segredo",
            {"event": "item/updated", "itemId": "x"},
            format="json",
            HTTP_HOST=tunnel,
        )
        assert response.status_code == 200, "o webhook precisa continuar acessivel"

    @pytest.mark.django_db
    def test_webhook_still_rejects_a_bad_token_through_the_tunnel(self, api, tunnel, monkeypatch):
        monkeypatch.setenv("PLUGGY_WEBHOOK_SECRET", "segredo")
        response = api.post(
            f"{WEBHOOK}?token=errado",
            {"event": "item/updated", "itemId": "x"},
            format="json",
            HTTP_HOST=tunnel,
        )
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_tunnel_host_reaches_health(self, api, tunnel):
        response = api.get("/health/", HTTP_HOST=tunnel)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_restriction_ignores_the_port(self, api, tunnel):
        response = api.get("/admin/", HTTP_HOST=f"{tunnel}:8000")
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_localhost_is_not_restricted(self, api, tunnel):
        """Desenvolvimento local nao pode ser afetado."""
        response = api.get("/api/v1/summary/", HTTP_HOST="localhost")
        # 401/403 = chegou na view e pediu autenticacao, nao foi bloqueado
        assert response.status_code in (401, 403)

    @pytest.mark.django_db
    def test_nothing_is_blocked_when_no_tunnel_host_is_configured(self, api, settings):
        settings.PUBLIC_TUNNEL_HOSTS = []
        response = api.get("/api/v1/summary/", HTTP_HOST="localhost")
        assert response.status_code in (401, 403)


class TestPublicRegistrationIsClosed:
    @pytest.mark.django_db
    def test_registration_returns_404_by_default(self, api, settings):
        settings.ALLOW_PUBLIC_REGISTRATION = False

        response = api.post(
            "/api/v1/auth/register/",
            {"email": "invasor@example.com", "password": "senha-forte-123"},
            format="json",
        )

        assert response.status_code == 404
        assert not get_user_model().objects.filter(email="invasor@example.com").exists()

    @pytest.mark.django_db
    def test_registration_works_when_explicitly_enabled(self, api, settings):
        settings.ALLOW_PUBLIC_REGISTRATION = True

        response = api.post(
            "/api/v1/auth/register/",
            {"email": "novo@example.com", "password": "senha-forte-123"},
            format="json",
        )

        assert response.status_code == 200
        assert get_user_model().objects.filter(email="novo@example.com").exists()


class TestLoginThrottling:
    @pytest.fixture(autouse=True)
    def clean_cache(self):
        cache.clear()
        yield
        cache.clear()

    @pytest.mark.django_db
    def test_token_endpoint_stops_brute_force(self, api):
        """Antes: senha podia ser tentada indefinidamente.

        Exercita a taxa real de DEFAULT_THROTTLE_RATES["login"], nao uma
        sobrescrita -- o api_settings do DRF nao recarrega com override de
        settings, e testar a config real e mais fiel.
        """
        from rest_framework.settings import api_settings

        rate = api_settings.DEFAULT_THROTTLE_RATES["login"]
        limit = int(rate.split("/")[0])

        statuses = []
        for _ in range(limit + 2):
            response = api.post(
                "/api/v1/auth/token/",
                {"username": "alvo@example.com", "password": "chute"},
                format="json",
            )
            statuses.append(response.status_code)

        assert 429 in statuses, f"nenhuma tentativa foi limitada em {rate}: {statuses}"
        assert statuses.index(429) <= limit, (
            f"limite aplicado depois de {statuses.index(429)} tentativas, "
            f"esperado no maximo {limit}"
        )

    @pytest.mark.django_db
    def test_a_valid_login_still_works_within_the_limit(self, api):
        get_user_model().objects.create_user(
            username="dono@example.com", email="dono@example.com", password="senha-forte-123"
        )

        response = api.post(
            "/api/v1/auth/token/",
            {"username": "dono@example.com", "password": "senha-forte-123"},
            format="json",
        )

        assert response.status_code == 200
        assert "access" in response.json()


class TestThrottlingExemptions:
    def test_webhook_has_throttling_disabled(self):
        """A Pluggy chega anonima e desiste apos 9 falhas -- um 429 perderia eventos."""
        from apps.finance.views import PluggyWebhookAPIView

        assert PluggyWebhookAPIView.throttle_classes == []

    def test_health_has_throttling_disabled(self):
        from apps.finance.views import HealthCheckAPIView

        assert HealthCheckAPIView.throttle_classes == []
