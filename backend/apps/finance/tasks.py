import logging
from datetime import date as date_type
from datetime import datetime, time, timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .consolidation import snapshot_net_worth
from .domain import (
    get_or_create_institution,
    normalize_transaction_category,
    refine_connection_institution,
)
from .models import (
    Account,
    AccountType,
    Card,
    ConnectionStatus,
    Investment,
    InvestmentPosition,
    PensionPlan,
    Subscription,
    SubscriptionPayment,
    SubscriptionStatus,
    SyncJob,
    SyncJobStatus,
    Transaction,
    TransactionType,
)
from .services import PluggyClient

logger = logging.getLogger(__name__)


def _parse_booked_at(raw_date: str | None) -> datetime:
    if not raw_date:
        return timezone.now()
    dt = parse_datetime(raw_date)
    if dt is None:
        parsed_d = parse_date(raw_date)
        if parsed_d is not None:
            dt = datetime.combine(parsed_d, time.min)
    if dt is None:
        dt = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _upsert_transaction(tx: dict, *, account, card, user) -> None:
    provider_category = tx.get("category", "") or ""
    Transaction.objects.update_or_create(
        external_id=tx["id"],
        defaults={
            "account": account,
            "card": card,
            "description": tx.get("description", "Transação"),
            "amount": tx.get("amount", 0) or 0,
            "currency": tx.get("currencyCode", "BRL"),
            "type": _normalize_transaction_type(tx.get("type")),
            "category": normalize_transaction_category(
                tx.get("description", ""),
                provider_category,
                _normalize_transaction_type(tx.get("type")),
                user=user,
            ),
            "provider_category": provider_category,
            "booked_at": _parse_booked_at(tx.get("date")),
        },
    )


def _broadcast_sync_event(user_id: int, status: str, connection_id: int, sync_job_id: int) -> None:
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "type": "sync_event",
            "status": status,
            "connection_id": connection_id,
            "sync_job_id": sync_job_id,
        },
    )


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


def _extract_day(date_str: str | None) -> int | None:
    if not date_str:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).day
    except (ValueError, AttributeError):
        return None


def _sync_card_transactions(client: PluggyClient, card: Card, from_date: str | None) -> None:
    card_external_id = str(card.external_id)
    try:
        transactions_data = client.fetch_account_transactions(card_external_id, from_date)
    except Exception as exc:
        if "410" in str(exc) or "404" in str(exc):
            logger.info(
                "Transactions not available (HTTP 410/404) for card %s (%s)",
                card.name,
                card_external_id,
            )
        else:
            logger.warning(
                "Error fetching transactions for card id=%s external_id=%s: %s",
                card.id,
                card_external_id,
                exc,
            )
        return

    for tx in transactions_data:
        _upsert_transaction(tx, account=None, card=card, user=card.connection.user)


def _due_date_for(year: int, month: int, due_day: int) -> date_type:
    if month == 2 and due_day > 28:
        due_day = 28
    elif month in (4, 6, 9, 11) and due_day > 30:
        due_day = 30
    try:
        return date_type(year, month, due_day)
    except ValueError:
        return date_type(year, month, 28)


def _reconcile_subscriptions(user) -> None:
    """Reconcile subscription payments against transactions.

    Runs on every sync, so it resolves the whole window in a fixed number of
    queries instead of one per (subscription, month) pair.
    """
    subscriptions = list(Subscription.objects.filter(user=user, is_active=True))
    if not subscriptions:
        return

    today = timezone.localdate()
    months: list[tuple[int, int]] = []
    for month_offset in range(-3, 7):
        year = today.year
        month = today.month + month_offset
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        months.append((year, month))

    wanted: dict[int, list[date_type]] = {
        sub.id: [_due_date_for(year, month, sub.due_day) for year, month in months]
        for sub in subscriptions
    }
    all_due_dates = [d for dates in wanted.values() for d in dates]
    window_start, window_end = min(all_due_dates), max(all_due_dates)

    existing = {
        (payment.subscription_id, payment.due_date): payment
        for payment in SubscriptionPayment.objects.filter(
            subscription__in=subscriptions,
            due_date__gte=window_start,
            due_date__lte=window_end,
        )
    }

    to_create = [
        SubscriptionPayment(
            subscription=sub,
            due_date=due_date,
            status=SubscriptionStatus.PENDING,
        )
        for sub in subscriptions
        for due_date in wanted[sub.id]
        if (sub.id, due_date) not in existing
    ]
    if to_create:
        SubscriptionPayment.objects.bulk_create(to_create, ignore_conflicts=True)
        for payment in SubscriptionPayment.objects.filter(
            subscription__in=subscriptions,
            due_date__gte=window_start,
            due_date__lte=window_end,
        ):
            existing[(payment.subscription_id, payment.due_date)] = payment

    transactions_by_date: dict[date_type, list[Transaction]] = {}
    for tx in Transaction.objects.filter(
        Q(account__connection__user=user) | Q(card__connection__user=user),
        booked_at__date__gte=window_start,
        booked_at__date__lte=window_end,
        amount__gt=0,
    ):
        transactions_by_date.setdefault(tx.booked_at.date(), []).append(tx)

    to_update: list[SubscriptionPayment] = []
    for sub in subscriptions:
        name = (sub.name or "").lower()
        category = (sub.category or "").lower()
        for due_date in wanted[sub.id]:
            payment = existing.get((sub.id, due_date))
            if payment is None:
                continue

            matching_tx = next(
                (
                    tx
                    for tx in transactions_by_date.get(due_date, ())
                    if (name and name in (tx.description or "").lower())
                    or (category and category in (tx.category or "").lower())
                ),
                None,
            )

            if matching_tx:
                payment.status = SubscriptionStatus.PAID
                payment.paid_date = matching_tx.booked_at.date()
                payment.paid_amount = matching_tx.amount
            elif due_date < today and payment.status == SubscriptionStatus.PENDING:
                payment.status = SubscriptionStatus.OVERDUE
            else:
                continue

            to_update.append(payment)

    if to_update:
        SubscriptionPayment.objects.bulk_update(to_update, ["status", "paid_date", "paid_amount"])


def _sync_pension_plans(client: PluggyClient, connection) -> None:
    try:
        investments_data = client.fetch_item_investments(connection.external_id)
    except Exception as exc:
        logger.warning(
            "Error fetching pension investments for connection external_id=%s: %s",
            connection.external_id,
            exc,
        )
        return

    for investment_data in investments_data:
        if investment_data.get("type", "").lower() in ("pension", "previdencia"):
            PensionPlan.objects.update_or_create(
                connection=connection,
                external_id=investment_data["id"],
                defaults={
                    "name": investment_data.get("name", "Previdência"),
                    "provider": investment_data.get("provider", ""),
                    "balance": investment_data.get("balance", 0) or 0,
                },
            )


@shared_task
def sync_connection_data(sync_job_id: int) -> None:
    sync_job = SyncJob.objects.select_related("connection").get(pk=sync_job_id)
    connection = sync_job.connection

    sync_job.status = SyncJobStatus.RUNNING
    sync_job.started_at = timezone.now()
    sync_job.save(update_fields=["status", "started_at", "updated_at"])
    _broadcast_sync_event(connection.user.id, "RUNNING", connection.id, sync_job.id)

    # Uma unica instancia reaproveita o cache da apiKey; instanciar por chamada
    # forcava um POST /auth novo a cada request.
    client = PluggyClient()

    try:
        try:
            item_data = client.fetch_item(connection.external_id)
            institution = get_or_create_institution(item_data)
            # Uma instituicao derivada (provider_id com ":") veio dos nomes das
            # contas, e e mais especifica que a do conector. Sobrescreve-la aqui
            # devolvia "MeuPluggy" no inicio de todo sync, deixando o nome errado
            # sempre que o refine no fim nao rodasse.
            already_derived = connection.institution_id is not None and ":" in str(
                connection.institution.provider_id
            )
            if not already_derived and (
                connection.institution != institution
                or (
                    connection.institution
                    and connection.institution.name.startswith("Instituição ")
                )
            ):
                connection.institution = institution
                connection.save(update_fields=["institution", "updated_at"])
        except Exception as exc:
            logger.warning(
                "Could not refresh institution details for connection %s: %s",
                connection.external_id,
                exc,
            )

        from_date = None
        if connection.last_synced_at:
            from_date = (connection.last_synced_at - timedelta(days=2)).date().isoformat()

        # Somente contas bancarias: as de credito vem de fetch_item_cards e sao
        # gravadas como Card. Sem o filtro, cada cartao virava Account e Card ao
        # mesmo tempo, duplicando saldo e alternando o vinculo das transacoes.
        accounts_data = client._request(
            "GET", "/accounts", params={"itemId": connection.external_id, "type": "BANK"}
        )
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
            try:
                transactions_data = client.fetch_account_transactions(
                    account_external_id, from_date
                )
            except Exception as exc:
                if "410" in str(exc) or "404" in str(exc):
                    logger.info(
                        "Transactions endpoint not available (HTTP 410/404) for account %s (%s)",
                        account.name,
                        account_external_id,
                    )
                else:
                    logger.warning(
                        "Error fetching transactions for account %s (%s): %s",
                        account.name,
                        account_external_id,
                        exc,
                    )
                continue

            for tx in transactions_data:
                _upsert_transaction(tx, account=account, card=None, user=connection.user)

        # A remocao de transacoes e responsabilidade do evento `transactions/deleted`,
        # que entrega os transactionIds exatos (ver process_pluggy_webhook).
        # Deletar por diferenca contra a janela de `from_date` apagaria todo o
        # historico anterior a ela.

        try:
            cards_data = client.fetch_item_cards(connection.external_id)
            for card_data in cards_data:
                credit_data = card_data.get("creditData", {}) or {}
                number = card_data.get("number", "")
                credit_limit = credit_data.get("creditLimit", card_data.get("credit_limit", 0))
                due_date = credit_data.get("balanceDueDate")
                close_date = credit_data.get("balanceCloseDate")
                card, _ = Card.objects.update_or_create(
                    external_id=card_data["id"],
                    defaults={
                        "connection": connection,
                        "name": card_data.get("name", "Cartão"),
                        "last4": number[-4:] if number else "",
                        "credit_limit": credit_limit or 0,
                        "current_balance": card_data.get("balance", 0) or 0,
                        "due_day": _extract_day(due_date),
                        "close_day": _extract_day(close_date),
                    },
                )
                _sync_card_transactions(client, card, from_date)
        except Exception as exc:
            logger.warning(
                "Error fetching cards for connection %s: %s",
                connection.external_id,
                exc,
            )

        # Precisa rodar depois de contas e cartoes: o nome do banco real so
        # aparece neles. Items do Meu Pluggy chegam todos como "MeuPluggy".
        try:
            refine_connection_institution(connection)
        except Exception as exc:
            logger.warning(
                "Could not refine institution for connection %s: %s",
                connection.external_id,
                exc,
            )

        try:
            investments_data = client.fetch_item_investments(connection.external_id)
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
        except Exception as exc:
            logger.warning(
                "Error fetching investments for connection %s: %s",
                connection.external_id,
                exc,
            )

        try:
            _sync_pension_plans(client, connection)
        except Exception as exc:
            logger.warning(
                "Error syncing pension plans for connection %s: %s",
                connection.external_id,
                exc,
            )

        if connection.user:
            try:
                _reconcile_subscriptions(connection.user)
            except Exception as exc:
                logger.warning("Error reconciling subscriptions: %s", exc)

            try:
                snapshot_net_worth(connection.user)
            except Exception as exc:
                logger.warning("Error taking net worth snapshot: %s", exc)

        connection.status = ConnectionStatus.ACTIVE
        connection.last_synced_at = timezone.now()
        connection.error_message = ""
        connection.save(update_fields=["status", "last_synced_at", "error_message", "updated_at"])

        sync_job.status = SyncJobStatus.SUCCESS
        sync_job.finished_at = timezone.now()
        sync_job.save(update_fields=["status", "finished_at", "updated_at"])
        _broadcast_sync_event(connection.user.id, "SUCCESS", connection.id, sync_job.id)
    except Exception as exc:
        connection.status = ConnectionStatus.ERROR
        connection.error_message = str(exc)
        connection.save(update_fields=["status", "error_message", "updated_at"])

        sync_job.status = SyncJobStatus.FAILED
        sync_job.error_message = str(exc)
        sync_job.finished_at = timezone.now()
        sync_job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        _broadcast_sync_event(connection.user.id, "FAILED", connection.id, sync_job.id)
        raise


@shared_task
def recompute_user_snapshot(user_id: int) -> None:
    user = get_user_model().objects.get(pk=user_id)
    snapshot_net_worth(user)


def _queue_full_sync(connection, reason: str) -> None:
    logger.info("Falling back to full sync for connection %s: %s", connection.external_id, reason)
    sync_job = SyncJob.objects.create(connection=connection, kind="incremental")
    sync_connection_data.delay(sync_job.id)


def _process_transaction_event(connection, event: str, payload: dict) -> None:
    """Handle `transactions/*` events using the ids/links the payload already carries.

    Falling back to a full sync on every transaction event would refetch every
    account, card and investment of the item for a handful of new rows.
    """
    if event == "transactions/deleted":
        transaction_ids = payload.get("transactionIds") or []
        if not transaction_ids:
            return
        deleted_count, _ = Transaction.objects.filter(
            Q(account__connection=connection) | Q(card__connection=connection),
            external_id__in=transaction_ids,
        ).delete()
        logger.info(
            "Deleted %d transactions for connection %s from webhook",
            deleted_count,
            connection.external_id,
        )
        return

    account_id = payload.get("accountId")
    if not account_id:
        _queue_full_sync(connection, "payload sem accountId")
        return

    account = Account.objects.filter(external_id=str(account_id), connection=connection).first()
    card = None
    if account is None:
        card = Card.objects.filter(external_id=str(account_id), connection=connection).first()
    if account is None and card is None:
        _queue_full_sync(connection, f"conta {account_id} ainda desconhecida localmente")
        return

    client = PluggyClient()
    try:
        if event == "transactions/created":
            link = payload.get("createdTransactionsLink")
            created_from = payload.get("transactionsCreatedAtFrom")
            if link:
                transactions = client.fetch_transactions_from_link(link)
            elif created_from:
                transactions = client.fetch_account_transactions(str(account_id), created_from)
            else:
                _queue_full_sync(connection, "payload sem link nem transactionsCreatedAtFrom")
                return
        else:
            transaction_ids = payload.get("transactionIds") or []
            if not transaction_ids:
                return
            transactions = client.fetch_transactions_by_ids(transaction_ids)
    except Exception as exc:
        logger.warning(
            "Error fetching transactions from webhook payload for connection %s: %s",
            connection.external_id,
            exc,
        )
        _queue_full_sync(connection, "falha ao buscar transacoes do payload")
        return

    for tx in transactions:
        _upsert_transaction(tx, account=account, card=card, user=connection.user)

    logger.info(
        "Applied %d transactions from %s for connection %s",
        len(transactions),
        event,
        connection.external_id,
    )


@shared_task
def process_pluggy_webhook(event, item_id, client_user_id, payload):
    from .domain import get_or_create_institution
    from .models import Connection, ConnectionStatus, ProcessedWebhookEvent
    from .services import PluggyClient

    logger.info(
        "Processing Pluggy webhook event=%s item_id=%s client_user_id=%s",
        event,
        item_id,
        client_user_id,
    )

    event_id = payload.get("eventId")
    if event_id:
        _, is_new = ProcessedWebhookEvent.objects.get_or_create(
            event_id=str(event_id),
            defaults={"event": event, "item_id": str(item_id)},
        )
        if not is_new:
            logger.info("Pluggy webhook eventId=%s already processed; skipping", event_id)
            return

    user = None
    if client_user_id:
        user_model = get_user_model()
        try:
            user = user_model.objects.get(pk=int(client_user_id))
        except (user_model.DoesNotExist, ValueError):
            user = None

    if event == "item/deleted":
        Connection.objects.filter(external_id=str(item_id)).delete()
        return

    if event in (
        "transactions/created",
        "transactions/updated",
        "transactions/deleted",
    ):
        connection = Connection.objects.filter(external_id=str(item_id)).first()
        if connection is None:
            logger.info("Pluggy webhook %s for unknown item %s; ignoring", event, item_id)
            return
        _process_transaction_event(connection, event, payload)
        return

    client = PluggyClient()
    try:
        item_data = client.fetch_item(item_id)
    except Exception as exc:
        logger.error("Pluggy webhook: failed to fetch item %s: %s", item_id, exc)
        return

    status = item_data.get("status", "")
    execution_status = item_data.get("executionStatus", "")
    institution = get_or_create_institution(item_data)

    if event == "item/error":
        error_data = item_data.get("error", {}) or payload.get("error", {})
        connection, _ = Connection.objects.get_or_create(
            external_id=str(item_id),
            defaults={
                "user": user,
                "institution": institution,
                "status": ConnectionStatus.ERROR,
            },
        )
        connection.status = ConnectionStatus.ERROR
        connection.error_message = error_data.get("message", "Unknown error")
        connection.save(update_fields=["status", "error_message", "updated_at"])
        return

    if status == "LOGIN_ERROR":
        connection, _ = Connection.objects.get_or_create(
            external_id=str(item_id),
            defaults={
                "user": user,
                "institution": institution,
                "status": ConnectionStatus.ERROR,
            },
        )
        connection.status = ConnectionStatus.ERROR
        connection.error_message = item_data.get("error", {}).get("message", "LOGIN_ERROR")
        connection.save(update_fields=["status", "error_message", "updated_at"])
        return

    if status == "OUTDATED":
        connection, _ = Connection.objects.get_or_create(
            external_id=str(item_id),
            defaults={
                "user": user,
                "institution": institution,
                "status": ConnectionStatus.ERROR,
            },
        )
        connection.status = ConnectionStatus.ERROR
        connection.error_message = f"OUTDATED: {item_data.get('error', {}).get('message', '')}"
        connection.save(update_fields=["status", "error_message", "updated_at"])
        return

    if status == "WAITING_USER_INPUT":
        connection, _ = Connection.objects.get_or_create(
            external_id=str(item_id),
            defaults={
                "user": user,
                "institution": institution,
                "status": ConnectionStatus.PENDING,
            },
        )
        connection.status = ConnectionStatus.PENDING
        connection.save(update_fields=["status", "updated_at"])
        return

    connection, created = Connection.objects.get_or_create(
        external_id=str(item_id),
        defaults={
            "user": user,
            "institution": institution,
            "status": ConnectionStatus.PENDING,
        },
    )

    if not created and user is not None and connection.user != user:
        connection.user = user
        connection.save(update_fields=["user", "updated_at"])

    if status == "UPDATED":
        if execution_status == "PARTIAL_SUCCESS":
            status_detail = item_data.get("statusDetail", {}) or {}
            for product, detail in status_detail.items():
                if detail and isinstance(detail, dict) and not detail.get("isUpdated"):
                    logger.warning(
                        "Product %s failed for item %s: %s",
                        product,
                        item_id,
                        detail.get("warnings"),
                    )

        connection.status = ConnectionStatus.ACTIVE
        connection.last_synced_at = timezone.now()
        connection.error_message = ""
        connection.save(
            update_fields=[
                "status",
                "last_synced_at",
                "error_message",
                "updated_at",
            ]
        )

        sync_job = SyncJob.objects.create(connection=connection, kind="full")
        sync_connection_data.delay(sync_job.id)
