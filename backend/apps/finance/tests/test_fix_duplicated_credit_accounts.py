"""Testes do comando fix_duplicated_credit_accounts.

O ponto critico: as transacoes precisam sobreviver. Deletar a Account
duplicada direto faria CASCADE e apagaria o historico do cartao.
"""

import pytest
from django.core.management import call_command

from apps.finance.models import (
    Account,
    AccountType,
    Card,
    Transaction,
    TransactionType,
)


@pytest.fixture
def duplicated_credit(db, connection):
    """Mesma conta de credito da Pluggy gravada como Account e como Card."""
    external_id = "acc-credito-1"
    account = Account.objects.create(
        connection=connection,
        external_id=external_id,
        name="ultraviolet-black",
        type=AccountType.CREDIT,
        balance=4549.21,
        # classify_account_balance() usa available_balance, nao balance.
        available_balance=4549.21,
    )
    card = Card.objects.create(
        connection=connection,
        external_id=external_id,
        name="ultraviolet-black",
        credit_limit=29750,
        current_balance=4549.21,
    )
    for i in range(3):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-{i}",
            description=f"Compra {i}",
            amount=100 + i,
            type=TransactionType.DEBIT,
            booked_at="2026-08-01T12:00:00Z",
        )
    return account, card


@pytest.mark.django_db
def test_dry_run_changes_nothing(duplicated_credit):
    account, _ = duplicated_credit

    call_command("fix_duplicated_credit_accounts")

    assert Account.objects.filter(pk=account.pk).exists()
    assert Transaction.objects.filter(account=account).count() == 3


@pytest.mark.django_db
def test_execute_repoints_transactions_and_removes_account(duplicated_credit):
    account, card = duplicated_credit

    call_command("fix_duplicated_credit_accounts", "--execute")

    assert not Account.objects.filter(pk=account.pk).exists()
    assert Transaction.objects.count() == 3, "transacoes foram apagadas por CASCADE"
    assert Transaction.objects.filter(card=card).count() == 3
    assert Transaction.objects.filter(account__isnull=False).count() == 0


@pytest.mark.django_db
def test_is_idempotent(duplicated_credit):
    call_command("fix_duplicated_credit_accounts", "--execute")
    call_command("fix_duplicated_credit_accounts", "--execute")

    assert Transaction.objects.count() == 3


@pytest.mark.django_db
def test_leaves_bank_accounts_untouched(db, connection, account):
    """Uma Account sem Card equivalente nao deve ser tocada."""
    Transaction.objects.create(
        account=account,
        external_id="tx-banco",
        description="Pix",
        amount=10,
        type=TransactionType.DEBIT,
        booked_at="2026-08-01T12:00:00Z",
    )

    call_command("fix_duplicated_credit_accounts", "--execute")

    assert Account.objects.filter(pk=account.pk).exists()
    assert Transaction.objects.filter(account=account).count() == 1


@pytest.mark.django_db
def test_liabilities_stop_being_double_counted(duplicated_credit, user):
    from decimal import Decimal

    from apps.finance.consolidation import build_user_financial_summary

    before = build_user_financial_summary(user)
    call_command("fix_duplicated_credit_accounts", "--execute")
    after = build_user_financial_summary(user)

    # Antes: 4549.21 (Account credit) + 4549.21 (Card) contados como passivo.
    assert before["liabilities"] == Decimal("9098.42")
    assert after["liabilities"] == Decimal("4549.21")
    assert after["net_worth"] - before["net_worth"] == Decimal("4549.21")
