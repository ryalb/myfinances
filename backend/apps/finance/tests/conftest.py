"""Fakes e fixtures compartilhados pelos testes de finance.

Sem mocking de biblioteca: o PluggyClient e substituido por um fake em memoria
que devolve payloads controlados.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.finance.models import (
    Account,
    AccountType,
    Connection,
    ConnectionStatus,
    FinancialInstitution,
    SyncJob,
)


class FakePluggyClient:
    """Client em memoria com a mesma superficie usada por tasks.py."""

    def __init__(
        self,
        *,
        item=None,
        accounts=None,
        transactions=None,
        cards=None,
        investments=None,
    ):
        self.item = item or {"id": "item-1", "status": "UPDATED", "connectorId": "200"}
        self.accounts = accounts if accounts is not None else []
        self.transactions = transactions if transactions is not None else {}
        self.cards = cards if cards is not None else []
        self.investments = investments if investments is not None else []
        self.auth_calls = 0
        self.requested_account_params: list[dict] = []

    def fetch_item(self, item_id):
        return self.item

    def _request(self, method, path, params=None):
        if path == "/accounts":
            self.requested_account_params.append(dict(params or {}))
            return self.accounts
        return []

    def fetch_account_transactions(self, account_id, from_date=None):
        return self.transactions.get(account_id, [])

    def fetch_item_cards(self, item_id):
        return self.cards

    def fetch_item_investments(self, item_id):
        return self.investments

    def fetch_transactions_from_link(self, link):
        return self.transactions.get("__link__", [])

    def fetch_transactions_by_ids(self, transaction_ids):
        by_id = {tx["id"]: tx for txs in self.transactions.values() for tx in txs}
        return [by_id[i] for i in transaction_ids if i in by_id]

    def _get_api_key(self):
        self.auth_calls += 1
        return "fake-api-key"

    def _invalidate_api_key(self):
        pass


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="dono", email="dono@example.com", password="senha-123"
    )


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        username="invasor", email="invasor@example.com", password="senha-123"
    )


@pytest.fixture
def institution(db):
    return FinancialInstitution.objects.create(name="Banco Teste", provider_id="200")


@pytest.fixture
def connection(db, user, institution):
    return Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-1",
        status=ConnectionStatus.PENDING,
    )


@pytest.fixture
def account(db, connection):
    return Account.objects.create(
        connection=connection,
        external_id="acc-1",
        name="Conta Corrente",
        type=AccountType.CHECKING,
        balance=1000,
    )


@pytest.fixture
def sync_job(db, connection):
    return SyncJob.objects.create(connection=connection, kind="full")
