"""Testes de persistencia do relatorio de IA.

`PortfolioReportAPIView.post` gerava o relatorio e so devolvia na resposta --
nada era gravado, e um refresh de pagina (ou so voltar depois) perdia a analise.
Cobre tambem o escopo por usuario do historico (`PortfolioReportViewSet`), pelo
mesmo motivo que qualquer lista escopada por usuario precisa de teste: sem
`get_queryset` filtrando por `user`, o historico de um vira visivel para outro.
"""

import pytest
from rest_framework.test import APIClient

from apps.finance.models import PortfolioReport

REPORT_URL = "/api/v1/ai/portfolio-report/"
HISTORY_URL = "/api/v1/ai/portfolio-reports/"


class FakeChunk:
    def __init__(self, source_type, source_id):
        self.source_type = source_type
        self.source_id = source_id


class FakeRAGService:
    def __init__(self, *args, **kwargs):
        pass

    def index_user_context(self, user):
        return {"indexed": 1, "skipped": 0, "removed": 0}

    def retrieve_report_context(self, user, query, top_k=6):
        return [{"chunk": FakeChunk("financial_summary", str(user.id)), "similarity": 1.0}]


class FakeLLMService:
    def __init__(self, *args, **kwargs):
        pass

    def generate_portfolio_report(self, context_chunks):
        return {
            "summary": "Tudo certo",
            "projections": "Deve melhorar",
            "strengths": ["Reserva boa"],
            "weaknesses": ["Gasto alto"],
            "adjustments": [],
            "suggestions": ["Tesouro Selic"],
            "disclaimer": "aviso",
            "sources": [{"source_type": "financial_summary", "source_id": "1", "similarity": 1.0}],
        }


@pytest.fixture(autouse=True)
def fake_ai_services(monkeypatch):
    # A view importa `RAGService`/`LLMService` de dentro de `post`, entao troca
    # no modulo de origem chega la sem precisar mockar o Ollama.
    monkeypatch.setattr("apps.finance.ai_services.RAGService", FakeRAGService)
    monkeypatch.setattr("apps.finance.ai_services.LLMService", FakeLLMService)


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_generating_a_report_persists_it(user):
    response = _client(user).post(REPORT_URL, {"query": "onde estou gastando"}, format="json")

    assert response.status_code == 200
    saved = PortfolioReport.objects.get(user=user)
    assert saved.query == "onde estou gastando"
    assert saved.summary == "Tudo certo"
    assert saved.suggestions == ["Tesouro Selic"]
    assert saved.sources == [{"source_type": "financial_summary", "source_id": "1", "similarity": 1.0}]
    assert response.data["id"] == saved.id
    assert response.data["index"] == {"indexed": 1, "skipped": 0, "removed": 0}


@pytest.mark.django_db
def test_generating_without_a_query_still_persists_the_default_used(user):
    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 200
    saved = PortfolioReport.objects.get(user=user)
    assert saved.query  # o default do endpoint, nao vazio


@pytest.mark.django_db
def test_history_lists_only_the_current_users_reports(user, other_user):
    PortfolioReport.objects.create(user=user, summary="meu relatorio")
    PortfolioReport.objects.create(user=other_user, summary="relatorio do outro")

    response = _client(user).get(HISTORY_URL)

    assert response.status_code == 200
    summaries = [item["summary"] for item in response.data["results"]]
    assert summaries == ["meu relatorio"]


@pytest.mark.django_db
def test_history_is_ordered_most_recent_first(user):
    older = PortfolioReport.objects.create(user=user, summary="mais antigo")
    newer = PortfolioReport.objects.create(user=user, summary="mais novo")

    response = _client(user).get(HISTORY_URL)

    ids = [item["id"] for item in response.data["results"]]
    assert ids == [newer.id, older.id]


@pytest.mark.django_db
def test_history_requires_authentication():
    response = APIClient().get(HISTORY_URL)

    assert response.status_code in (401, 403)
