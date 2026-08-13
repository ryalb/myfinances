"""Testes de persistencia da orientacao do construtor de portfolio.

Mesma razao de ser de `test_future_projection_report.py`: uma orientacao por
usuario (`user` como `OneToOneField`); "Reanalisar" substitui a orientacao
anterior em vez de acumular historico.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.finance.models import (
    Investment,
    InvestmentPosition,
    PortfolioBuilderReport,
    PortfolioTarget,
)

REPORT_URL = "/api/v1/ai/portfolio-builder/"


class FakeChunk:
    def __init__(self, source_type, source_id):
        self.source_type = source_type
        self.source_id = source_id


class FakeRAGService:
    def __init__(self, *args, **kwargs):
        pass

    def index_user_context(self, user):
        return {"indexed": 1, "skipped": 0, "removed": 0}

    def retrieve_portfolio_builder_context(self, user):
        return [{"chunk": FakeChunk("financial_summary", str(user.id)), "similarity": 1.0}]


class FakeLLMService:
    def __init__(self, *args, **kwargs):
        pass

    def generate_portfolio_builder_guidance(self, context_chunks, drift):
        return {
            "guidance": "Sua carteira esta concentrada em renda fixa",
            "rebalancing_actions": ["Direcione o próximo aporte para ações"],
            "common_mistakes": [],
            "disclaimer": "aviso",
            "sources": [{"source_type": "financial_summary", "source_id": "1", "similarity": 1.0}],
        }


@pytest.fixture(autouse=True)
def fake_ai_services(monkeypatch):
    monkeypatch.setattr("apps.finance.ai_services.RAGService", FakeRAGService)
    monkeypatch.setattr("apps.finance.ai_services.LLMService", FakeLLMService)


@pytest.fixture
def with_allocation_data(user, connection):
    PortfolioTarget.objects.create(
        user=user, asset_class="fixed_income", target_percentage=Decimal("100")
    )
    investment = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Tesouro Selic", kind="FIXED_INCOME"
    )
    InvestmentPosition.objects.create(
        investment=investment,
        as_of_date="2026-08-01",
        quantity=1,
        unit_price=1000,
        market_value=1000,
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_generating_guidance_persists_it(user, with_allocation_data):
    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 200, response.data
    saved = PortfolioBuilderReport.objects.get(user=user)
    assert saved.guidance == "Sua carteira esta concentrada em renda fixa"
    assert saved.rebalancing_actions == ["Direcione o próximo aporte para ações"]
    assert saved.drift[0]["asset_class"] == "fixed_income"
    assert response.data["id"] == saved.id
    assert response.data["index"] == {"indexed": 1, "skipped": 0, "removed": 0}


@pytest.mark.django_db
def test_generating_without_allocation_data_returns_422(user):
    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 422
    assert not PortfolioBuilderReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_reanalyzing_replaces_the_previous_guidance_instead_of_accumulating(
    user, with_allocation_data
):
    first = _client(user).post(REPORT_URL, {}, format="json")

    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 200
    assert PortfolioBuilderReport.objects.filter(user=user).count() == 1
    assert response.data["id"] == first.data["id"]


@pytest.mark.django_db
def test_get_returns_the_persisted_guidance(user, with_allocation_data):
    _client(user).post(REPORT_URL, {}, format="json")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 200
    assert response.data["guidance"] == "Sua carteira esta concentrada em renda fixa"
    assert "index" not in response.data


@pytest.mark.django_db
def test_get_returns_404_when_nothing_was_generated_yet(user):
    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_only_returns_the_current_users_guidance(user, other_user):
    PortfolioBuilderReport.objects.create(user=other_user, guidance="do outro")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_requires_authentication():
    response = APIClient().get(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_deleting_the_guidance_removes_it(user):
    PortfolioBuilderReport.objects.create(user=user, guidance="para apagar")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 204
    assert not PortfolioBuilderReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_deleting_does_not_affect_another_users_guidance(user, other_user):
    other_report = PortfolioBuilderReport.objects.create(user=other_user, guidance="do outro")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 404
    assert PortfolioBuilderReport.objects.filter(id=other_report.id).exists()


@pytest.mark.django_db
def test_delete_requires_authentication():
    response = APIClient().delete(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_generate_requires_authentication():
    response = APIClient().post(REPORT_URL, {}, format="json")

    assert response.status_code in (401, 403)
