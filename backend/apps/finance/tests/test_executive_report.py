"""Testes de persistencia do relatorio executivo.

Mesma razao de ser de `test_portfolio_builder_report.py`: um relatorio por
usuario (`user` como `OneToOneField`); "Reanalisar" substitui o relatorio
anterior em vez de acumular historico. Unico ponto que diverge dos outros tres
relatorios de IA: o POST tambem depende de um valor de aporte (`contribution_
amount`), que pode vir do corpo da requisicao ou do calculo default
(`build_recent_month_averages`) -- os dois caminhos tem teste proprio.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.finance.models import ExecutiveReport, Investment, InvestmentPosition, PortfolioTarget

REPORT_URL = "/api/v1/ai/executive-report/"


class FakeChunk:
    def __init__(self, source_type, source_id):
        self.source_type = source_type
        self.source_id = source_id


class FakeRAGService:
    def __init__(self, *args, **kwargs):
        pass

    def index_user_context(self, user):
        return {"indexed": 1, "skipped": 0, "removed": 0}

    def retrieve_executive_report_context(self, user):
        return [{"chunk": FakeChunk("financial_summary", str(user.id)), "similarity": 1.0}]


class FakeLLMService:
    def __init__(self, *args, **kwargs):
        pass

    def generate_executive_report(self, context_chunks, drift, projection, contribution_plan):
        return {
            "summary": "Sua carteira faz sentido para o objetivo de longo prazo",
            "goal_fit": ["A reserva de emergência está alinhada com a meta de viagem"],
            "performance_verdict": ["O fundo de renda fixa rende abaixo do CDI, vale reavaliar"],
            "contribution_rationale": ["Direcione o aporte para renda fixa para reduzir o desvio"],
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
def test_generating_report_persists_it(user, with_allocation_data):
    response = _client(user).post(REPORT_URL, {"contribution_amount": "500.00"}, format="json")

    assert response.status_code == 200, response.data
    saved = ExecutiveReport.objects.get(user=user)
    assert saved.summary == "Sua carteira faz sentido para o objetivo de longo prazo"
    assert saved.goal_fit == ["A reserva de emergência está alinhada com a meta de viagem"]
    assert saved.performance_verdict == [
        "O fundo de renda fixa rende abaixo do CDI, vale reavaliar"
    ]
    assert saved.contribution_amount == Decimal("500.00")
    # Alvo 100% ja cumprido pela posicao existente: aporte extra some inteiro
    # no rateio por alvo (unica classe), nao ha o que "precisar" mais.
    assert saved.contribution_plan[0]["asset_class"] == "fixed_income"
    assert response.data["id"] == saved.id
    assert response.data["index"] == {"indexed": 1, "skipped": 0, "removed": 0}


@pytest.mark.django_db
def test_generating_without_allocation_target_returns_422(user, connection):
    Investment.objects.create(
        connection=connection, external_id="inv-1", name="Tesouro Selic", kind="FIXED_INCOME"
    )

    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 422
    assert not ExecutiveReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_generating_without_contribution_amount_and_no_savings_returns_422(
    user, with_allocation_data
):
    response = _client(user).post(REPORT_URL, {}, format="json")

    assert response.status_code == 422
    assert not ExecutiveReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_generating_with_explicit_contribution_amount_ignores_default(user, with_allocation_data):
    response = _client(user).post(REPORT_URL, {"contribution_amount": "1234.56"}, format="json")

    assert response.status_code == 200, response.data
    assert ExecutiveReport.objects.get(user=user).contribution_amount == Decimal("1234.56")


@pytest.mark.django_db
def test_reanalyzing_replaces_the_previous_report_instead_of_accumulating(
    user, with_allocation_data
):
    first = _client(user).post(REPORT_URL, {"contribution_amount": "500.00"}, format="json")

    response = _client(user).post(REPORT_URL, {"contribution_amount": "800.00"}, format="json")

    assert response.status_code == 200
    assert ExecutiveReport.objects.filter(user=user).count() == 1
    assert response.data["id"] == first.data["id"]
    assert ExecutiveReport.objects.get(user=user).contribution_amount == Decimal("800.00")


@pytest.mark.django_db
def test_get_returns_the_persisted_report(user, with_allocation_data):
    _client(user).post(REPORT_URL, {"contribution_amount": "500.00"}, format="json")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 200
    assert response.data["summary"] == "Sua carteira faz sentido para o objetivo de longo prazo"
    assert "index" not in response.data


@pytest.mark.django_db
def test_get_returns_404_when_nothing_was_generated_yet(user):
    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_only_returns_the_current_users_report(user, other_user):
    ExecutiveReport.objects.create(user=other_user, summary="do outro")

    response = _client(user).get(REPORT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_requires_authentication():
    response = APIClient().get(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_deleting_the_report_removes_it(user):
    ExecutiveReport.objects.create(user=user, summary="para apagar")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 204
    assert not ExecutiveReport.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_deleting_does_not_affect_another_users_report(user, other_user):
    other_report = ExecutiveReport.objects.create(user=other_user, summary="do outro")

    response = _client(user).delete(REPORT_URL)

    assert response.status_code == 404
    assert ExecutiveReport.objects.filter(id=other_report.id).exists()


@pytest.mark.django_db
def test_delete_requires_authentication():
    response = APIClient().delete(REPORT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_generate_requires_authentication():
    response = APIClient().post(REPORT_URL, {}, format="json")

    assert response.status_code in (401, 403)
