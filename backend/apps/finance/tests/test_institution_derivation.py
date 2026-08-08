"""Testes da derivacao de instituicao a partir das contas sincronizadas.

Items do Meu Pluggy chegam todos com connectorId=200 e connector.name
"MeuPluggy", entao sem isto toda conexao colapsa numa instituicao unica.
"""

import pytest

from apps.finance.domain import (
    derive_institution_from_names,
    refine_connection_institution,
)
from apps.finance.models import (
    Account,
    AccountType,
    Card,
    Connection,
    ConnectionStatus,
    FinancialInstitution,
)


class TestDeriveFromNames:
    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            (["Nu Pagamentos S.A. - Instituição de Pagamento"], "Nubank"),
            (["ultraviolet-black"], "Nubank"),
            (["Cartão Rico Visa Infinite"], "Rico Investimentos"),
            (["Conta Corrente Itaú"], "Itaú"),
            (["Banco Inter - Conta Digital"], "Banco Inter"),
            (["C6 Bank"], "C6 Bank"),
            (["BTG Pactual Digital"], "BTG Pactual"),
        ],
    )
    def test_matches_known_institutions(self, names, expected):
        derived = derive_institution_from_names(names)
        assert derived is not None, f"nao casou: {names}"
        assert derived[1] == expected

    def test_returns_none_for_unknown(self):
        assert derive_institution_from_names(["Banco Fictício XYZ"]) is None

    def test_returns_none_for_empty(self):
        assert derive_institution_from_names([]) is None
        assert derive_institution_from_names(["", None]) is None

    def test_does_not_match_substrings(self):
        """`inter` nao deve casar dentro de outras palavras."""
        assert derive_institution_from_names(["Conta Internacional"]) is None


@pytest.fixture
def meupluggy_institution(db):
    return FinancialInstitution.objects.create(name="MeuPluggy", provider_id="200")


@pytest.fixture
def meupluggy_connection(db, user, meupluggy_institution):
    return Connection.objects.create(
        user=user,
        institution=meupluggy_institution,
        external_id="item-nubank",
        status=ConnectionStatus.ACTIVE,
    )


class TestRefineConnectionInstitution:
    @pytest.mark.django_db
    def test_derives_nubank_from_account_name(self, meupluggy_connection):
        Account.objects.create(
            connection=meupluggy_connection,
            external_id="acc-nu",
            name="Nu Pagamentos S.A. - Instituição de Pagamento",
            type=AccountType.CHECKING,
        )

        institution = refine_connection_institution(meupluggy_connection)

        assert institution is not None
        assert institution.name == "Nubank"
        assert institution.provider_id == "200:nubank"
        meupluggy_connection.refresh_from_db()
        assert meupluggy_connection.institution_id == institution.id

    @pytest.mark.django_db
    def test_derives_from_card_when_there_is_no_account(self, meupluggy_connection):
        Card.objects.create(
            connection=meupluggy_connection,
            external_id="card-rico",
            name="Cartão Rico Visa Infinite",
        )

        institution = refine_connection_institution(meupluggy_connection)

        assert institution.name == "Rico Investimentos"
        assert institution.provider_id == "200:rico"

    @pytest.mark.django_db
    def test_two_connections_get_distinct_institutions(self, user, meupluggy_institution):
        nubank_conn = Connection.objects.create(
            user=user,
            institution=meupluggy_institution,
            external_id="item-nu",
            status=ConnectionStatus.ACTIVE,
        )
        Account.objects.create(
            connection=nubank_conn,
            external_id="acc-nu",
            name="Nu Pagamentos S.A. - Instituição de Pagamento",
            type=AccountType.CHECKING,
        )
        rico_conn = Connection.objects.create(
            user=user,
            institution=meupluggy_institution,
            external_id="item-rico",
            status=ConnectionStatus.ACTIVE,
        )
        Card.objects.create(
            connection=rico_conn, external_id="card-rico", name="Cartão Rico Visa Infinite"
        )

        refine_connection_institution(nubank_conn)
        refine_connection_institution(rico_conn)

        nubank_conn.refresh_from_db()
        rico_conn.refresh_from_db()
        assert nubank_conn.institution.name == "Nubank"
        assert rico_conn.institution.name == "Rico Investimentos"
        assert nubank_conn.institution_id != rico_conn.institution_id

    @pytest.mark.django_db
    def test_is_idempotent_and_does_not_nest_the_namespace(self, meupluggy_connection):
        Account.objects.create(
            connection=meupluggy_connection,
            external_id="acc-nu",
            name="Nu Pagamentos S.A. - Instituição de Pagamento",
            type=AccountType.CHECKING,
        )

        refine_connection_institution(meupluggy_connection)
        meupluggy_connection.refresh_from_db()
        refine_connection_institution(meupluggy_connection)
        meupluggy_connection.refresh_from_db()

        assert meupluggy_connection.institution.provider_id == "200:nubank"
        assert FinancialInstitution.objects.filter(provider_id__startswith="200:").count() == 1

    @pytest.mark.django_db
    def test_falls_back_to_the_bank_account_name(self, meupluggy_connection):
        Account.objects.create(
            connection=meupluggy_connection,
            external_id="acc-x",
            name="Banco Fictício XYZ - Conta Corrente",
            type=AccountType.CHECKING,
        )

        institution = refine_connection_institution(meupluggy_connection)

        assert institution.name == "Banco Fictício XYZ"
        assert institution.provider_id == "200:banco-ficticio-xyz"

    @pytest.mark.django_db
    def test_does_nothing_without_accounts_or_cards(self, meupluggy_connection):
        assert refine_connection_institution(meupluggy_connection) is None
        meupluggy_connection.refresh_from_db()
        assert meupluggy_connection.institution.name == "MeuPluggy"


class TestSyncDoesNotClobberDerivedInstitution:
    """O inicio do sync reescrevia a instituicao para a do conector.

    Isso devolvia "MeuPluggy" em todo sync, e o nome derivado so voltava se o
    refine no fim rodasse -- deixando o nome errado a cada falha intermediaria.
    """

    @pytest.mark.django_db
    def test_second_sync_keeps_the_derived_institution(self, monkeypatch, user, sync_job):
        from apps.finance import tasks

        from .conftest import FakePluggyClient

        connection = sync_job.connection
        client = FakePluggyClient(
            item={"id": connection.external_id, "status": "UPDATED", "connectorId": "200"},
            accounts=[
                {
                    "id": "acc-nu",
                    "name": "Nu Pagamentos S.A. - Instituição de Pagamento",
                    "type": "BANK",
                    "balance": 100,
                }
            ],
        )
        monkeypatch.setattr(tasks, "PluggyClient", lambda *a, **k: client)

        tasks.sync_connection_data(sync_job.id)
        connection.refresh_from_db()
        assert connection.institution.name == "Nubank"

        second = tasks.SyncJob.objects.create(connection=connection, kind="full")
        tasks.sync_connection_data(second.id)
        connection.refresh_from_db()

        assert (
            connection.institution.name == "Nubank"
        ), "o segundo sync reverteu a instituicao para a do conector"
        assert connection.institution.provider_id == "200:nubank"


class TestRefineCommand:
    @pytest.mark.django_db
    def test_repairs_a_connection_stuck_on_the_connector_name(self, meupluggy_connection, capsys):
        from django.core.management import call_command

        Account.objects.create(
            connection=meupluggy_connection,
            external_id="acc-nu",
            name="Nu Pagamentos S.A. - Instituição de Pagamento",
            type=AccountType.CHECKING,
        )

        call_command("pluggy_refine_institutions")

        meupluggy_connection.refresh_from_db()
        assert meupluggy_connection.institution.name == "Nubank"

    @pytest.mark.django_db
    def test_dry_run_changes_nothing(self, meupluggy_connection):
        from django.core.management import call_command

        Account.objects.create(
            connection=meupluggy_connection,
            external_id="acc-nu",
            name="Nu Pagamentos S.A. - Instituição de Pagamento",
            type=AccountType.CHECKING,
        )

        call_command("pluggy_refine_institutions", "--dry-run")

        meupluggy_connection.refresh_from_db()
        assert meupluggy_connection.institution.name == "MeuPluggy"
