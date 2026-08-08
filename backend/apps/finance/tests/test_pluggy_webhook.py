"""Testes de regressao do endpoint e do processamento de webhook da Pluggy."""

import pytest
from rest_framework.test import APIClient

from apps.finance import tasks
from apps.finance.models import (
    Account,
    AccountType,
    Connection,
    ConnectionStatus,
    FinancialInstitution,
    ProcessedWebhookEvent,
    Transaction,
    TransactionType,
)

from .conftest import FakePluggyClient

WEBHOOK_URL = "/api/v1/pluggy/webhook/"
SECRET = "segredo-de-teste"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setenv("PLUGGY_WEBHOOK_SECRET", SECRET)
    return SECRET


@pytest.fixture(autouse=True)
def no_celery_dispatch(monkeypatch):
    """Impede que .delay() tente falar com o broker durante os testes."""
    monkeypatch.setattr(tasks.sync_connection_data, "delay", lambda *a, **k: None)


class TestWebhookEndpointAuth:
    @pytest.mark.django_db
    def test_rejects_request_without_token(self, api, webhook_secret):
        """Antes: o endpoint era AllowAny sem validacao nenhuma."""
        response = api.post(
            WEBHOOK_URL,
            {"event": "item/updated", "itemId": "item-1"},
            format="json",
        )
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_rejects_request_with_wrong_token(self, api, webhook_secret):
        response = api.post(
            f"{WEBHOOK_URL}?token=errado",
            {"event": "item/updated", "itemId": "item-1"},
            format="json",
        )
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_returns_503_when_secret_is_not_configured(self, api, monkeypatch):
        monkeypatch.delenv("PLUGGY_WEBHOOK_SECRET", raising=False)
        response = api.post(
            f"{WEBHOOK_URL}?token=qualquer",
            {"event": "item/updated", "itemId": "item-1"},
            format="json",
        )
        assert response.status_code == 503

    @pytest.mark.django_db
    def test_accepts_request_with_valid_token(self, api, webhook_secret, monkeypatch):
        queued = {}
        monkeypatch.setattr(
            tasks.process_pluggy_webhook,
            "delay",
            lambda *args, **kwargs: queued.setdefault("args", args),
        )
        response = api.post(
            f"{WEBHOOK_URL}?token={SECRET}",
            {"event": "item/updated", "itemId": "item-1", "clientUserId": "1"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json() == {"status": "queued"}
        assert queued["args"][0] == "item/updated"

    @pytest.mark.django_db
    def test_ignores_unknown_events(self, api, webhook_secret):
        response = api.post(
            f"{WEBHOOK_URL}?token={SECRET}",
            {"event": "item.update", "itemId": "item-1"},
            format="json",
        )
        assert response.json() == {"status": "ignored"}


class TestTransactionDeletionScope:
    @pytest.mark.django_db
    def test_deletion_is_scoped_to_the_items_own_connection(self, connection, account, other_user):
        """Antes: filter(external_id__in=ids).delete() sem escopo -- um webhook
        podia apagar transacoes de qualquer usuario."""
        mine = Transaction.objects.create(
            account=account,
            external_id="tx-minha",
            description="Minha",
            amount=10,
            type=TransactionType.DEBIT,
            booked_at="2026-08-01T12:00:00Z",
        )
        other_institution = FinancialInstitution.objects.create(
            name="Outro Banco", provider_id="999"
        )
        other_connection = Connection.objects.create(
            user=other_user,
            institution=other_institution,
            external_id="item-outro",
            status=ConnectionStatus.ACTIVE,
        )
        other_account = Account.objects.create(
            connection=other_connection,
            external_id="acc-outro",
            name="Conta do outro",
            type=AccountType.CHECKING,
        )
        theirs = Transaction.objects.create(
            account=other_account,
            external_id="tx-do-outro",
            description="Do outro",
            amount=10,
            type=TransactionType.DEBIT,
            booked_at="2026-08-01T12:00:00Z",
        )

        tasks._process_transaction_event(
            connection,
            "transactions/deleted",
            {"transactionIds": ["tx-minha", "tx-do-outro"]},
        )

        assert not Transaction.objects.filter(pk=mine.pk).exists()
        assert Transaction.objects.filter(
            pk=theirs.pk
        ).exists(), "webhook apagou transacao de outra conexao"


class TestTransactionEventEfficiency:
    @pytest.mark.django_db
    def test_created_event_uses_the_payload_link(self, connection, account, monkeypatch):
        """Antes: qualquer transactions/* disparava um sync completo do item."""
        client = FakePluggyClient(
            transactions={
                "__link__": [
                    {
                        "id": "tx-link",
                        "date": "2026-08-05",
                        "amount": 42,
                        "description": "Via link",
                        "type": "DEBIT",
                    }
                ]
            }
        )
        monkeypatch.setattr(tasks, "PluggyClient", lambda *a, **k: client)
        full_syncs = []
        monkeypatch.setattr(
            tasks, "_queue_full_sync", lambda conn, reason: full_syncs.append(reason)
        )

        tasks._process_transaction_event(
            connection,
            "transactions/created",
            {
                "accountId": "acc-1",
                "createdTransactionsLink": "https://api.pluggy.ai/transactions?x=1",
            },
        )

        assert full_syncs == [], f"caiu em sync completo: {full_syncs}"
        tx = Transaction.objects.get(external_id="tx-link")
        assert tx.account_id == account.id

    @pytest.mark.django_db
    def test_falls_back_to_full_sync_when_account_is_unknown(self, connection, monkeypatch):
        full_syncs = []
        monkeypatch.setattr(
            tasks, "_queue_full_sync", lambda conn, reason: full_syncs.append(reason)
        )

        tasks._process_transaction_event(
            connection,
            "transactions/created",
            {"accountId": "acc-desconhecida", "createdTransactionsLink": "x"},
        )

        assert len(full_syncs) == 1


class TestIdempotency:
    @pytest.mark.django_db
    def test_repeated_event_id_is_processed_only_once(self, connection, monkeypatch):
        """A Pluggy reentrega webhooks ate 9 vezes."""
        calls = []
        monkeypatch.setattr(
            tasks,
            "_process_transaction_event",
            lambda conn, event, payload: calls.append(event),
        )
        payload = {
            "eventId": "evt-123",
            "accountId": "acc-1",
            "transactionIds": ["tx-1"],
        }

        tasks.process_pluggy_webhook("transactions/deleted", "item-1", None, payload)
        tasks.process_pluggy_webhook("transactions/deleted", "item-1", None, payload)

        assert calls == ["transactions/deleted"]
        assert ProcessedWebhookEvent.objects.filter(event_id="evt-123").count() == 1
