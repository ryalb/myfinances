"""Testes de regressao de autorizacao nos endpoints Pluggy."""

import pytest
from rest_framework.test import APIClient

from apps.finance import views

REGENERATE_URL = "/api/v1/pluggy/regenerate-auth/"


class StubClient:
    def __init__(self, *args, **kwargs):
        pass

    def _get_api_key(self):
        return "chave-secreta-de-acesso-total"

    def _invalidate_api_key(self):
        pass


@pytest.fixture
def stub_client(monkeypatch):
    holder = {}

    def factory(*args, **kwargs):
        client = holder.get("client")
        if client is None:
            client = StubClient()
            holder["client"] = client
        return client

    monkeypatch.setattr(views, "PluggyClient", factory)
    monkeypatch.setattr(views.sync_connection_data, "delay", lambda *a, **k: None)
    return holder


# A cobertura de autorizacao do antigo /pluggy/discover/ migrou para
# test_pluggy_import_item_api.py: o endpoint foi substituido por
# /api/v1/pluggy/items/, que recebe o itemId em vez de listar.


class TestRegenerateAuthDoesNotLeakApiKey:
    @pytest.mark.django_db
    def test_response_never_contains_the_api_key(self, stub_client, django_user_model):
        """Antes: a resposta devolvia a apiKey, que o frontend logava no console
        e renderizava na tela."""
        admin = django_user_model.objects.create_user(
            username="admin", email="admin@example.com", password="x", is_staff=True
        )
        api = APIClient()
        api.force_authenticate(admin)

        response = api.post(REGENERATE_URL, {}, format="json")

        assert response.status_code == 200
        body = response.json()
        assert "apiKey" not in body
        assert "chave-secreta-de-acesso-total" not in response.content.decode()

    @pytest.mark.django_db
    def test_is_denied_to_non_staff_users(self, stub_client, user):
        api = APIClient()
        api.force_authenticate(user)
        response = api.post(REGENERATE_URL, {}, format="json")
        assert response.status_code == 403


class TestDebugTokenEndpointIsGone:
    @pytest.mark.django_db
    def test_debug_token_route_no_longer_exists(self):
        """Antes: criava um superusuario com email hardcoded e emitia JWT sem auth."""
        response = APIClient().post("/api/v1/auth/debug-token/", {}, format="json")
        assert response.status_code == 404
