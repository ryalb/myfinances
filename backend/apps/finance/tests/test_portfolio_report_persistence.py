"""Testes de persistencia do relatorio de IA.

`PortfolioReportAPIView.post` gera e persiste o relatorio. A partir da mudanca
para "uma analise por usuario" (`user` como `OneToOneField`), gerar de novo
("Reanalisar" no frontend) substitui a analise anterior em vez de acumular
historico -- por isso o foco destes testes e "so existe uma linha por usuario,
sempre a mais recente", nao mais paginacao/lista.
"""

import pytest
from rest_framework.test import APIClient

from apps.finance.models import PortfolioReport

REPORT_URL = "/api/v1/ai/portfolio-report/"


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
    assert saved.sources == [
        {"source_type": "financial_summary", "source_id": "1", "similarity": 1.0}
    ]
    assert response.data["id"] == saved.id
    assert response.data["index"] == {"indexed": 1, "skipped": 0, "removed": 0}


@pytest.mark.django_db
def test_generating_without_a_query_still_persists_the_default_used(user):
    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 200
    saved = PortfolioReport.objects.get(user=user)
    assert saved.query  # o default do endpoint, nao vazio


@pytest.mark.django_db
def test_reanalyzing_replaces_the_previous_report_instead_of_accumulating(user):
    """"Reanalisar": a segunda geracao substitui a primeira, nunca acumula."""
    first = _client(user).post(REPORT_URL, {"query": "primeira pergunta"}, format="json")

    response = _client(user).post(REPORT_URL, {"query": "segunda pergunta"}, format="json")

    assert response.status_code == 200
    assert PortfolioReport.objects.filter(user=user).count() == 1
    saved = PortfolioReport.objects.get(user=user)
    assert saved.query == "segunda pergunta"
    # Mesmo id: update_or_create atualiza a linha existente, nao cria outra.
    assert saved.id == first.data["id"]


@pytest.mark.django_db
def test_get_returns_the_persisted_report(user):
    _client(user).post(REPORT_URL, {"query": "onde estou gastando"}, format="json")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 200
    assert response.data["query"] == "onde estou gastando"
    # `index` so existe na resposta de geracao (POST), nao no relatorio persistido.
    assert "index" not in response.data


@pytest.mark.django_db
def test_get_returns_404_when_nothing_was_generated_yet(user):
    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_only_returns_the_current_users_report(user, other_user):
    PortfolioReport.objects.create(user=other_user, summary="relatorio do outro")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_requires_authentication():
    response = APIClient().get(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_deleting_the_report_removes_it(user):
    PortfolioReport.objects.create(user=user, summary="para apagar")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 204
    assert not PortfolioReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_deleting_does_not_affect_another_users_report(user, other_user):
    other_report = PortfolioReport.objects.create(user=other_user, summary="do outro")

    response = _client(user).delete(REPORT_URL)

    # Nao ha relatorio do proprio usuario para apagar -- 404, e o do outro
    # usuario continua intacto (o filtro por `user` nem chega a ve-lo).
    assert response.status_code == 404
    assert PortfolioReport.objects.filter(id=other_report.id).exists()


@pytest.mark.django_db
def test_delete_requires_authentication():
    response = APIClient().delete(REPORT_URL)

    assert response.status_code in (401, 403)
