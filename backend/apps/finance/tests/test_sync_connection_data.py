"""Testes de regressao do sync de conexoes Pluggy.

Cada teste aqui trava um bug que existia e quebrava a sincronizacao.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.finance import tasks
from apps.finance.models import (
    Account,
    ConnectionStatus,
    SyncJobStatus,
    Transaction,
    TransactionType,
)

from .conftest import FakePluggyClient


def _tx(tx_id, date_iso, amount=100, description="Compra"):
    return {
        "id": tx_id,
        "date": date_iso,
        "amount": amount,
        "description": description,
        "currencyCode": "BRL",
        "type": "DEBIT",
        "category": "Shopping",
    }


@pytest.fixture
def fake_client(monkeypatch):
    """Instala um FakePluggyClient configuravel no lugar do real."""
    holder = {}

    def install(client):
        holder["client"] = client
        monkeypatch.setattr(tasks, "PluggyClient", lambda *a, **k: client)
        return client

    return install


@pytest.mark.django_db
def test_sync_completes_when_account_has_transactions(fake_client, sync_job, connection):
    """Antes: Transaction.objects.filter(connection=...) levantava FieldError
    (o model nao tem esse campo) e abortava todo o sync na primeira conta."""
    fake_client(
        FakePluggyClient(
            accounts=[{"id": "acc-1", "name": "Conta", "type": "BANK", "balance": 500}],
            transactions={"acc-1": [_tx("tx-1", "2026-08-01")]},
        )
    )

    tasks.sync_connection_data(sync_job.id)

    sync_job.refresh_from_db()
    connection.refresh_from_db()
    assert sync_job.status == SyncJobStatus.SUCCESS
    assert sync_job.error_message == ""
    assert connection.status == ConnectionStatus.ACTIVE
    assert connection.last_synced_at is not None
    assert Account.objects.filter(external_id="acc-1").exists()
    assert Transaction.objects.filter(external_id="tx-1").exists()


@pytest.mark.django_db
def test_incremental_sync_preserves_history_outside_window(
    fake_client, sync_job, connection, account
):
    """Antes: o sync apagava toda transacao fora da janela de `from_date`
    (last_synced_at - 2 dias), destruindo o historico."""
    old = Transaction.objects.create(
        account=account,
        external_id="tx-antiga",
        description="Compra antiga",
        amount=50,
        type=TransactionType.DEBIT,
        booked_at=timezone.now() - timedelta(days=200),
    )
    connection.last_synced_at = timezone.now() - timedelta(hours=1)
    connection.save(update_fields=["last_synced_at"])

    fake_client(
        FakePluggyClient(
            accounts=[{"id": "acc-1", "name": "Conta", "type": "BANK", "balance": 500}],
            transactions={"acc-1": [_tx("tx-nova", timezone.now().date().isoformat())]},
        )
    )

    tasks.sync_connection_data(sync_job.id)

    assert Transaction.objects.filter(
        pk=old.pk
    ).exists(), "transacao historica foi apagada pelo sync incremental"
    assert Transaction.objects.filter(external_id="tx-nova").exists()


@pytest.mark.django_db
def test_sync_requests_only_bank_accounts(fake_client, sync_job):
    """Antes: /accounts sem filtro trazia as contas CREDIT, que tambem viravam
    Card via fetch_item_cards -- mesma conta gravada duas vezes."""
    client = fake_client(FakePluggyClient(accounts=[]))

    tasks.sync_connection_data(sync_job.id)

    assert client.requested_account_params, "nenhuma chamada a /accounts"
    assert client.requested_account_params[0].get("type") == "BANK"


@pytest.mark.django_db
def test_sync_reuses_a_single_client(fake_client, sync_job):
    """Antes: PluggyClient() era instanciado 9x, forcando um POST /auth por chamada."""
    client = fake_client(
        FakePluggyClient(
            accounts=[{"id": "acc-1", "name": "Conta", "type": "BANK", "balance": 10}],
            transactions={"acc-1": [_tx("tx-1", "2026-08-01")]},
        )
    )

    tasks.sync_connection_data(sync_job.id)

    # O fake nao autentica sozinho; o que importa e que a mesma instancia
    # atendeu todas as chamadas do sync.
    assert client.requested_account_params == [
        {"itemId": "item-1", "type": "BANK"}
    ], "o sync deveria usar uma unica instancia de client"


@pytest.mark.django_db
def test_sync_marks_job_failed_and_reraises_on_error(fake_client, sync_job, connection):
    class ExplodingClient(FakePluggyClient):
        def _request(self, method, path, params=None):
            raise RuntimeError("boom")

    fake_client(ExplodingClient())

    with pytest.raises(RuntimeError):
        tasks.sync_connection_data(sync_job.id)

    sync_job.refresh_from_db()
    connection.refresh_from_db()
    assert sync_job.status == SyncJobStatus.FAILED
    assert "boom" in sync_job.error_message
    assert connection.status == ConnectionStatus.ERROR
