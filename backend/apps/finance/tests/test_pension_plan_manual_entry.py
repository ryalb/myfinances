"""Lancamento manual de previdencia privada.

Previdencia (PGBL/VGBL) fica no Open Insurance (Susep), fora do Open Finance que a
Pluggy cobre -- a sincronizacao automatica normalmente nunca traz esse dado (ver
`test_pension_sync.py`). `PensionPlanViewSet` virou `ModelViewSet` para permitir
cadastro manual, escopado ao usuario e com `connection=None`. Planos que vieram
sincronizados (`connection` preenchido) so devem mudar pelo sync, entao a escrita
manual bloqueia editar/excluir esses.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.finance.models import PensionPlan

PENSION_PLANS_URL = "/api/v1/pension-plans/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def synced_plan(db, connection):
    return PensionPlan.objects.create(
        connection=connection,
        user=connection.user,
        external_id="inv-prev-1",
        name="Previdência sincronizada",
        provider="Seguradora X",
        balance=1000,
    )


@pytest.fixture
def their_synced_plan(db, other_user, institution):
    from apps.finance.models import Connection, ConnectionStatus

    their_connection = Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-do-outro-pension",
        status=ConnectionStatus.ACTIVE,
    )
    return PensionPlan.objects.create(
        connection=their_connection,
        user=other_user,
        external_id="inv-prev-2",
        name="Previdência do invasor",
        provider="Seguradora Y",
        balance=5000,
    )


@pytest.mark.django_db
def test_can_create_a_manual_pension_plan(api, user):
    response = api.post(
        PENSION_PLANS_URL,
        {"name": "Previdência Icatu", "provider": "Icatu Seguros", "balance": "2500.00"},
        format="json",
    )

    assert response.status_code == 201, response.data
    plan = PensionPlan.objects.get(pk=response.data["id"])
    assert plan.user_id == user.id
    assert plan.connection_id is None
    assert response.data["is_manual"] is True


@pytest.mark.django_db
def test_cannot_set_connection_on_create(api):
    """`connection` nao e mais um campo do serializer -- o cliente nao decide isso."""
    response = api.post(
        PENSION_PLANS_URL,
        {
            "name": "Tentativa",
            "provider": "Seguradora Z",
            "balance": "10.00",
            "connection": 999,
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    plan = PensionPlan.objects.get(pk=response.data["id"])
    assert plan.connection_id is None


@pytest.mark.django_db
def test_can_edit_a_manual_pension_plan(api, user):
    plan = PensionPlan.objects.create(
        user=user, name="Antigo saldo", provider="Icatu Seguros", balance=100
    )

    response = api.patch(f"{PENSION_PLANS_URL}{plan.id}/", {"balance": "999.99"}, format="json")

    assert response.status_code == 200, response.data
    plan.refresh_from_db()
    assert plan.balance == Decimal("999.99")


@pytest.mark.django_db
def test_can_delete_a_manual_pension_plan(api, user):
    plan = PensionPlan.objects.create(user=user, name="Removível", provider="X", balance=1)

    response = api.delete(f"{PENSION_PLANS_URL}{plan.id}/")

    assert response.status_code == 204, response.data
    assert not PensionPlan.objects.filter(pk=plan.id).exists()


@pytest.mark.django_db
def test_cannot_edit_a_synced_pension_plan(api, synced_plan):
    response = api.patch(
        f"{PENSION_PLANS_URL}{synced_plan.id}/", {"balance": "1.00"}, format="json"
    )

    assert response.status_code == 403, response.data
    synced_plan.refresh_from_db()
    assert synced_plan.balance == 1000


@pytest.mark.django_db
def test_cannot_delete_a_synced_pension_plan(api, synced_plan):
    response = api.delete(f"{PENSION_PLANS_URL}{synced_plan.id}/")

    assert response.status_code == 403, response.data
    assert PensionPlan.objects.filter(pk=synced_plan.id).exists()


@pytest.mark.django_db
def test_synced_plan_is_listed_as_not_manual(api, synced_plan):
    response = api.get(f"{PENSION_PLANS_URL}{synced_plan.id}/")

    assert response.status_code == 200, response.data
    assert response.data["is_manual"] is False


@pytest.mark.django_db
def test_someone_elses_pension_plan_stays_invisible(api, their_synced_plan):
    assert api.get(f"{PENSION_PLANS_URL}{their_synced_plan.id}/").status_code == 404
    assert api.patch(
        f"{PENSION_PLANS_URL}{their_synced_plan.id}/", {"balance": "1.00"}, format="json"
    ).status_code == 404
    assert api.delete(f"{PENSION_PLANS_URL}{their_synced_plan.id}/").status_code == 404
    assert PensionPlan.objects.filter(pk=their_synced_plan.id).exists()
