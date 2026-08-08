"""Testes do endpoint que substituiu /pluggy/discover/.

O discover dependia de `GET /items`, que a Pluggy nao expoe (401). O novo
endpoint recebe o itemId explicitamente.
"""

import pytest
from rest_framework.test import APIClient

from apps.finance import views
from apps.finance.models import Connection, ConnectionStatus, SyncJob

URL = "/api/v1/pluggy/items/"
ITEM_ID = "05187d4e-9824-45d5-af32-85c3fc1e1abd"


class StubClient:
    def __init__(self, *args, item=None, fail=False, **kwargs):
        self.item = item or {
            "id": ITEM_ID,
            "status": "UPDATED",
            "connectorId": "200",
            "connector": {"id": 200, "name": "MeuPluggy"},
        }
        self.fail = fail

    def fetch_item(self, item_id):
        if self.fail:
            raise RuntimeError("401 Unauthorized")
        return self.item


@pytest.fixture
def stub(monkeypatch):
    holder = {"client": StubClient()}
    monkeypatch.setattr(views, "PluggyClient", lambda *a, **k: holder["client"])
    monkeypatch.setattr(views.sync_connection_data, "delay", lambda *a, **k: None)
    return holder


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class TestImportItem:
    @pytest.mark.django_db
    def test_creates_connection_and_queues_sync(self, api, stub, user):
        response = api.post(URL, {"itemId": ITEM_ID}, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["created"] is True
        assert body["external_id"] == ITEM_ID
        assert body["status"] == ConnectionStatus.ACTIVE

        connection = Connection.objects.get(external_id=ITEM_ID)
        assert connection.user_id == user.id
        assert SyncJob.objects.filter(connection=connection, kind="full").exists()

    @pytest.mark.django_db
    def test_is_idempotent_for_the_same_owner(self, api, stub):
        api.post(URL, {"itemId": ITEM_ID}, format="json")
        response = api.post(URL, {"itemId": ITEM_ID}, format="json")

        assert response.status_code == 200
        assert response.json()["created"] is False
        assert Connection.objects.filter(external_id=ITEM_ID).count() == 1

    @pytest.mark.django_db
    def test_rejects_missing_item_id(self, api, stub):
        response = api.post(URL, {}, format="json")
        assert response.status_code == 400
        assert "itemId" in response.json()["error"]

    @pytest.mark.django_db
    def test_rejects_non_uuid(self, api, stub):
        response = api.post(URL, {"itemId": "nao-e-uuid"}, format="json")
        assert response.status_code == 400
        assert "UUID" in response.json()["error"]

    @pytest.mark.django_db
    def test_refuses_item_owned_by_another_user(self, api, stub, other_user, institution):
        Connection.objects.create(
            user=other_user,
            institution=institution,
            external_id=ITEM_ID,
            status=ConnectionStatus.ACTIVE,
        )

        response = api.post(URL, {"itemId": ITEM_ID}, format="json")

        assert response.status_code == 409
        Connection.objects.get(external_id=ITEM_ID).refresh_from_db()
        assert Connection.objects.get(external_id=ITEM_ID).user_id == other_user.id

    @pytest.mark.django_db
    def test_returns_502_when_pluggy_rejects_the_item(self, api, stub):
        stub["client"] = StubClient(fail=True)

        response = api.post(URL, {"itemId": ITEM_ID}, format="json")

        assert response.status_code == 502
        assert not Connection.objects.filter(external_id=ITEM_ID).exists()

    @pytest.mark.django_db
    def test_marks_connection_pending_when_item_is_not_updated(self, api, stub):
        stub["client"] = StubClient(
            item={"id": ITEM_ID, "status": "LOGIN_ERROR", "connectorId": "200"}
        )

        response = api.post(URL, {"itemId": ITEM_ID}, format="json")

        assert response.status_code == 201
        assert response.json()["status"] == ConnectionStatus.PENDING
        assert "LOGIN_ERROR" in response.json()["message"]

    @pytest.mark.django_db
    def test_requires_authentication(self, stub):
        response = APIClient().post(URL, {"itemId": ITEM_ID}, format="json")
        assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_old_discover_route_is_gone():
    response = APIClient().post("/api/v1/pluggy/discover/", {}, format="json")
    assert response.status_code == 404
