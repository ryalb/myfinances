"""Correcao do nome exibido para contas sem apelido proprio: quando o banco
manda `name` generico (igual ao label do tipo, ex. "Conta Corrente" para toda
conta corrente), a tela usa `institution_name` para distinguir contas do
mesmo tipo em instituicoes diferentes -- ver `AccountSerializer.institution_name`
e o fallback em `frontend/pages/accounts.vue`.
"""

import pytest
from rest_framework.test import APIClient

from apps.finance.models import Account, AccountType

ACCOUNTS_URL = "/api/v1/accounts/"


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_account_serializer_exposes_institution_name(api, connection, institution):
    Account.objects.create(
        connection=connection,
        external_id="acc-1",
        name="Conta Corrente",
        type=AccountType.CHECKING,
    )

    response = api.get(ACCOUNTS_URL)

    assert response.status_code == 200
    assert response.data[0]["institution_name"] == institution.name


@pytest.mark.django_db
def test_account_institution_name_is_scoped_to_its_own_connection(
    api, user, connection, institution
):
    from apps.finance.models import Connection, ConnectionStatus, FinancialInstitution

    other_institution = FinancialInstitution.objects.create(name="Outro Banco", provider_id="203")
    other_connection = Connection.objects.create(
        user=user,
        institution=other_institution,
        external_id="item-4",
        status=ConnectionStatus.PENDING,
    )
    Account.objects.create(connection=connection, external_id="acc-1", name="Conta Corrente")
    Account.objects.create(connection=other_connection, external_id="acc-2", name="Conta Corrente")

    response = api.get(ACCOUNTS_URL)

    names = {row["institution_name"] for row in response.data}
    assert names == {institution.name, "Outro Banco"}
