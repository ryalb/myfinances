from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .consolidation import snapshot_net_worth
from .domain import normalize_transaction_category
from .models import (
    Account,
    AccountType,
    Card,
    Investment,
    InvestmentPosition,
    SyncJob,
    SyncJobStatus,
    Transaction,
    TransactionType,
)
from .services import PluggyClient


def _normalize_account_type(raw_type: str | None) -> str:
    value = (raw_type or "").lower()
    mapping = {
        "checking": AccountType.CHECKING,
        "savings": AccountType.SAVINGS,
        "brokerage": AccountType.BROKERAGE,
        "credit": AccountType.CREDIT,
        "bank": AccountType.CHECKING,
        "investment": AccountType.BROKERAGE,
    }
    return mapping.get(value, AccountType.OTHER)


def _normalize_transaction_type(raw_type: str | None) -> str:
    value = (raw_type or "").lower()
    mapping = {
        "debit": TransactionType.DEBIT,
        "credit": TransactionType.CREDIT,
        "expense": TransactionType.DEBIT,
        "income": TransactionType.CREDIT,
    }
    return mapping.get(value, TransactionType.DEBIT)


@shared_task
def sync_connection_data(sync_job_id: int) -> None:
    sync_job = SyncJob.objects.select_related("connection").get(pk=sync_job_id)
    connection = sync_job.connection

    sync_job.status = SyncJobStatus.RUNNING
    sync_job.started_at = timezone.now()
    sync_job.save(update_fields=["status", "started_at", "updated_at"])

    try:
        from_date = None
        if connection.last_synced_at:
            from_date = (connection.last_synced_at - timedelta(days=2)).date().isoformat()

        accounts_data = PluggyClient().fetch_item_accounts(connection.external_id)
        account_map: dict[str, Account] = {}

        for item in accounts_data:
            account, _ = Account.objects.update_or_create(
                external_id=item["id"],
                defaults={
                    "connection": connection,
                    "name": item.get("name", "Conta"),
                    "type": _normalize_account_type(item.get("type")),
                    "currency": item.get("currencyCode", "BRL"),
                    "balance": item.get("balance", 0) or 0,
                    "available_balance": item.get("availableBalance", item.get("balance", 0)) or 0,
                },
            )
            account_map[account.external_id] = account

        for account_external_id, account in account_map.items():
            transactions_data = PluggyClient().fetch_account_transactions(
                account_external_id, from_date=from_date
            )
            for tx in transactions_data:
                provider_category = tx.get("category", "") or ""
                normalized_category = normalize_transaction_category(
                    tx.get("description", ""),
                    provider_category,
                    _normalize_transaction_type(tx.get("type")),
                )
                booked_at = parse_datetime(tx.get("date", ""))
                if booked_at is None:
                    booked_at = timezone.now()
                Transaction.objects.update_or_create(
                    external_id=tx["id"],
                    defaults={
                        "account": account,
                        "description": tx.get("description", "Transação"),
                        "amount": tx.get("amount", 0) or 0,
                        "currency": tx.get("currencyCode", "BRL"),
                        "type": _normalize_transaction_type(tx.get("type")),
                        "category": normalized_category,
                        "provider_category": provider_category,
                        "booked_at": booked_at,
                    },
                )

        cards_data = PluggyClient().fetch_item_cards(connection.external_id)
        for card in cards_data:
            Card.objects.update_or_create(
                external_id=card["id"],
                defaults={
                    "connection": connection,
                    "name": card.get("name", "Cartão"),
                    "last4": card.get("last4", ""),
                    "credit_limit": card.get("creditLimit", 0) or 0,
                    "current_balance": card.get("balance", 0) or 0,
                    "due_day": card.get("dueDay"),
                    "close_day": card.get("closeDay"),
                },
            )

        investments_data = PluggyClient().fetch_item_investments(connection.external_id)
        today = timezone.localdate()
        for investment_data in investments_data:
            investment, _ = Investment.objects.update_or_create(
                external_id=investment_data["id"],
                defaults={
                    "connection": connection,
                    "name": investment_data.get("name", "Investimento"),
                    "kind": investment_data.get("type", "other"),
                    "currency": investment_data.get("currencyCode", "BRL"),
                },
            )
            InvestmentPosition.objects.update_or_create(
                investment=investment,
                as_of_date=today,
                defaults={
                    "quantity": investment_data.get("quantity", 0) or 0,
                    "unit_price": investment_data.get("price", 0) or 0,
                    "market_value": investment_data.get("balance", 0) or 0,
                },
            )

        connection.status = "active"
        connection.last_synced_at = timezone.now()
        connection.error_message = ""
        connection.save(update_fields=["status", "last_synced_at", "error_message", "updated_at"])

        snapshot_net_worth(connection.user)

        sync_job.status = SyncJobStatus.SUCCESS
        sync_job.finished_at = timezone.now()
        sync_job.save(update_fields=["status", "finished_at", "updated_at"])
    except Exception as exc:
        connection.status = "error"
        connection.error_message = str(exc)
        connection.save(update_fields=["status", "error_message", "updated_at"])

        sync_job.status = SyncJobStatus.FAILED
        sync_job.error_message = str(exc)
        sync_job.finished_at = timezone.now()
        sync_job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        raise


@shared_task
def recompute_user_snapshot(user_id: int) -> None:
    user = get_user_model().objects.get(pk=user_id)
    snapshot_net_worth(user)
