"""Testes de persistencia da narracao do simulador de futuro financeiro.

Mesma razao de ser de `test_portfolio_report_persistence.py`: uma narracao por
usuario (`user` como `OneToOneField`); "Reanalisar" substitui a narracao
anterior em vez de acumular historico.
"""

import pytest
from rest_framework.test import APIClient

from apps.finance.models import FutureProjectionReport

REPORT_URL = "/api/v1/ai/future-projection/"


class FakeChunk:
    def __init__(self, source_type, source_id):
        self.source_type = source_type
        self.source_id = source_id


class FakeRAGService:
    def __init__(self, *args, **kwargs):
        pass

    def index_user_context(self, user):
        return {"indexed": 1, "skipped": 0, "removed": 0}

    def retrieve_future_projection_context(self, user):
        return [{"chunk": FakeChunk("financial_summary", str(user.id)), "similarity": 1.0}]


class FakeLLMService:
    def __init__(self, *args, **kwargs):
        pass

    def generate_future_projection_narrative(self, context_chunks, projection_data):
        return {
            "narrative": "Tudo indica que voce vai bem",
            "leverage_explanation": ["Aumentar a poupança ajuda bastante"],
            "goal_commentary": [],
            "disclaimer": "aviso",
            "sources": [{"source_type": "financial_summary", "source_id": "1", "similarity": 1.0}],
        }


@pytest.fixture(autouse=True)
def fake_ai_services(monkeypatch):
    monkeypatch.setattr("apps.finance.ai_services.RAGService", FakeRAGService)
    monkeypatch.setattr("apps.finance.ai_services.LLMService", FakeLLMService)


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_generating_a_narrative_persists_it(user):
    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 200, response.data
    saved = FutureProjectionReport.objects.get(user=user)
    assert saved.narrative == "Tudo indica que voce vai bem"
    assert saved.leverage_explanation == ["Aumentar a poupança ajuda bastante"]
    assert saved.sources == [
        {"source_type": "financial_summary", "source_id": "1", "similarity": 1.0}
    ]
    assert saved.projection["horizons"] == [5, 10, 20]
    assert response.data["id"] == saved.id
    assert response.data["index"] == {"indexed": 1, "skipped": 0, "removed": 0}


@pytest.mark.django_db
def test_reanalyzing_replaces_the_previous_narrative_instead_of_accumulating(user):
    first = _client(user).post(REPORT_URL, {}, format="json")

    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 200
    assert FutureProjectionReport.objects.filter(user=user).count() == 1
    assert response.data["id"] == first.data["id"]


@pytest.mark.django_db
def test_get_returns_the_persisted_narrative(user):
    _client(user).post(REPORT_URL, {}, format="json")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 200
    assert response.data["narrative"] == "Tudo indica que voce vai bem"
    assert "index" not in response.data


@pytest.mark.django_db
def test_get_returns_404_when_nothing_was_generated_yet(user):
    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_only_returns_the_current_users_narrative(user, other_user):
    FutureProjectionReport.objects.create(user=other_user, narrative="do outro")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_requires_authentication():
    response = APIClient().get(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_deleting_the_narrative_removes_it(user):
    FutureProjectionReport.objects.create(user=user, narrative="para apagar")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 204
    assert not FutureProjectionReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_deleting_does_not_affect_another_users_narrative(user, other_user):
    other_report = FutureProjectionReport.objects.create(user=other_user, narrative="do outro")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 404
    assert FutureProjectionReport.objects.filter(id=other_report.id).exists()


@pytest.mark.django_db
def test_delete_requires_authentication():
    response = APIClient().delete(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_generate_requires_authentication():
    response = APIClient().post(REPORT_URL, {}, format="json")

    assert response.status_code in (401, 403)
