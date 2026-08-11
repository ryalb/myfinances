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
    Identity,
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


def _parse_date_only(raw_date: str | None) -> date_type | None:
    if not raw_date:
        return None
    return _parse_booked_at(raw_date).date()


def _int_or_none(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _upsert_transaction(tx: dict, *, account, card, user) -> None:
    provider_category = tx.get("category", "") or ""
    tx_type = _normalize_transaction_type(tx.get("type"))
    merchant = tx.get("merchant") or {}
    credit_card_metadata = tx.get("creditCardMetadata") or {}
    payment_data = tx.get("paymentData") or {}
    Transaction.objects.update_or_create(
        external_id=tx["id"],
        defaults={
            "account": account,
            "card": card,
            "description": tx.get("description", "Transação"),
            # Magnitude, nao valor com sinal.
            #
            # A Pluggy assina `amount` e a convencao **difere** entre conta e cartao:
            # em conta a saida e negativa; em cartao a compra e positiva e o
            # pagamento da fatura e negativo. O indicador confiavel de direcao e
            # `type` (DEBIT = saida, CREDIT = entrada), que e obrigatorio.
            #
            # Guardar com sinal fazia `Sum(amount)` das despesas dar negativo (taxa
            # de poupanca acima de 100%), o prefixo "-" da tela virar "--", e a
            # reconciliacao de assinaturas nunca casar, porque ela filtra amount > 0.
            "amount": abs(tx.get("amount", 0) or 0),
            "currency": tx.get("currencyCode", "BRL"),
            "type": tx_type,
            "category": normalize_transaction_category(
                tx.get("description", ""),
                provider_category,
                tx_type,
                user=user,
            ),
            "provider_category": provider_category,
            "booked_at": _parse_booked_at(tx.get("date")),
            # Campos crus da Pluggy sem uso na tela hoje -- ver comentario em
            # `Transaction` (models.py) sobre o uso pelo relatorio de IA.
            "description_raw": tx.get("descriptionRaw") or "",
            "amount_in_account_currency": tx.get("amountInAccountCurrency"),
            "balance_after": tx.get("balance"),
            "provider_code": tx.get("providerCode") or "",
            "status": tx.get("status") or "",
            "operation_type": tx.get("operationType") or "",
            "operation_type_additional_info": tx.get("operationTypeAdditionalInfo") or "",
            "provider_transaction_id": tx.get("providerId") or "",
            "merchant_name": merchant.get("name") or "",
            "merchant_business_name": merchant.get("businessName") or "",
            "merchant_cnpj": merchant.get("cnpj") or "",
            "merchant_cnae": merchant.get("cnae") or "",
            "installment_number": _int_or_none(credit_card_metadata.get("installmentNumber")),
            "installment_total": _int_or_none(credit_card_metadata.get("totalInstallments")),
            "installment_total_amount": credit_card_metadata.get("totalAmount"),
            "purchase_date": (
                _parse_booked_at(credit_card_metadata["purchaseDate"])
                if credit_card_metadata.get("purchaseDate")
                else None
            ),
            "payee_mcc": credit_card_metadata.get("payeeMCC") or "",
            "bill_id": credit_card_metadata.get("billId") or "",
            "bill_forecast_date": credit_card_metadata.get("billForecastDate") or "",
            "payment_method": payment_data.get("paymentMethod") or "",
            "payment_reason": payment_data.get("reason") or "",
            "payment_reference_number": payment_data.get("referenceNumber") or "",
            "payment_authentication_code": payment_data.get("authenticationCode") or "",
            "payment_payer": payment_data.get("payer") or {},
            "payment_receiver": payment_data.get("receiver") or {},
        },
    )


def _primary_contact(items: list[dict] | None) -> dict:
    """Primeiro contato marcado como principal, ou o primeiro da lista.

    A Pluggy pode devolver mais de um email/telefone/endereco por titular;
    sem um criterio de escolha o sync gravaria dados de forma inconsistente
    a cada execucao, na ordem em que a API decidir devolver a lista.
    """
    if not items:
        return {}
    for item in items:
        if item.get("primary") or (item.get("type") or "").upper() == "PERSONAL":
            return item
    return items[0]


def _upsert_identity(connection, identity_data: dict) -> None:
    document = identity_data.get("taxNumber") or identity_data.get("document") or ""
    document_type = identity_data.get("documentType") or ("CPF" if document else "")

    birth_date = None
    raw_birth_date = identity_data.get("birthDate")
    if raw_birth_date:
        birth_date = _parse_booked_at(raw_birth_date).date()

    qualifications = identity_data.get("qualifications") or {}
    informed_income = qualifications.get("informedIncome") or {}
    informed_patrimony = qualifications.get("informedPatrimony") or {}
    marital_status = identity_data.get("maritalStatus") or {}

    Identity.objects.update_or_create(
        connection=connection,
        defaults={
            "external_id": identity_data.get("id") or "",
            "full_name": identity_data.get("fullName") or "",
            "document": document,
            "document_type": document_type,
            "birth_date": birth_date,
            "job_title": identity_data.get("jobTitle") or "",
            "email": _primary_contact(identity_data.get("emails")).get("value") or "",
            "phone_number": _primary_contact(identity_data.get("phoneNumbers")).get("value") or "",
            "address": _primary_contact(identity_data.get("addresses")).get("fullAddress") or "",
            # Campos crus da Pluggy sem uso na tela hoje -- ver comentario em
            # `Identity` (models.py) sobre o uso pelo relatorio de IA.
            "investor_profile": identity_data.get("investorProfile") or "",
            "sex": identity_data.get("sex") or "",
            "marital_status": marital_status.get("code") or "",
            "social_name": identity_data.get("socialName") or "",
            "occupation_description": qualifications.get("occupationDescription") or "",
            "informed_income_amount": informed_income.get("amount"),
            "informed_income_frequency": informed_income.get("frequency") or "",
            "informed_patrimony_amount": informed_patrimony.get("amount"),
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


def _normalize_account_type(raw_type: str | None, raw_subtype: str | None = None) -> str:
    # `subtype` distingue CHECKINGS_ACCOUNT de SAVINGS_ACCOUNT; `type` sozinho e
    # sempre "BANK" (o /accounts e filtrado por type=BANK), o que fazia toda
    # conta poupanca cair em CHECKING por falta de sinal mais especifico.
    subtype_mapping = {
        "checkings_account": AccountType.CHECKING,
        "savings_account": AccountType.SAVINGS,
        "credit_card": AccountType.CREDIT,
    }
    normalized_subtype = subtype_mapping.get((raw_subtype or "").lower())
    if normalized_subtype:
        return normalized_subtype

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


# Debito real raramente cai exatamente no dia calculado (fim de semana, atraso de
# lancamento, dia de corte do cartao). 5 dias cobre isso e ainda fica bem abaixo da
# distancia entre vencimentos de meses consecutivos (~28-31 dias), entao as janelas
# de dois meses da mesma assinatura nao se sobrepoem.
RECONCILE_MATCH_TOLERANCE_DAYS = 5


def _candidate_transactions(
    transactions_by_date: dict[date_type, list[Transaction]], due_date: date_type
) -> list[Transaction]:
    candidates = []
    for offset in range(-RECONCILE_MATCH_TOLERANCE_DAYS, RECONCILE_MATCH_TOLERANCE_DAYS + 1):
        candidates.extend(transactions_by_date.get(due_date + timedelta(days=offset), ()))
    return candidates


def _best_match(
    sub: Subscription,
    due_date: date_type,
    candidates: list[Transaction],
    used_transaction_ids: set[int],
) -> Transaction | None:
    name = (sub.name or "").lower()
    category = (sub.category or "").lower()

    matches = [
        tx
        for tx in candidates
        if tx.id not in used_transaction_ids
        and (
            # Bidirecional: o nome da assinatura costuma levar um sufixo que o
            # usuario adiciona so para desambiguar duas cobrancas iguais (ex.:
            # "Claro Flex - Ryan" e "Claro Flex - Sheyla" quando as duas linhas
            # chegam do banco como a mesma descricao "Claro Flex"). Exigir a
            # string inteira do nome dentro da descricao nunca casava nesse caso.
            (
                name
                and (tx.description or "")
                and (
                    name in (tx.description or "").lower()
                    or (tx.description or "").lower() in name
                )
            )
            or (category and category in (tx.category or "").lower())
        )
        # `payment_account` so referencia Account, nunca Card -- uma transacao de
        # cartao (account_id is None) nao tem como ser escopada por ele, e excluir
        # esses candidatos travava o match de toda assinatura paga no cartao.
        and (
            sub.payment_account_id is None
            or tx.account_id is None
            or tx.account_id == sub.payment_account_id
        )
    ]
    if not matches:
        return None

    return min(
        matches,
        key=lambda tx: (
            abs((tx.booked_at.date() - due_date).days),
            abs(tx.amount - sub.amount),
        ),
    )


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

    tolerance = timedelta(days=RECONCILE_MATCH_TOLERANCE_DAYS)
    transactions_by_date: dict[date_type, list[Transaction]] = {}
    for tx in Transaction.objects.filter(
        Q(account__connection__user=user) | Q(card__connection__user=user),
        booked_at__date__gte=window_start - tolerance,
        booked_at__date__lte=window_end + tolerance,
        amount__gt=0,
    ):
        transactions_by_date.setdefault(tx.booked_at.date(), []).append(tx)

    to_update: list[SubscriptionPayment] = []
    # Uma transacao so serve para um pagamento -- sem isto, a janela mais larga
    # deixaria duas assinaturas com nome/categoria parecidos (ex.: dois
    # streamings) reclamarem o mesmo debito.
    used_transaction_ids: set[int] = set()
    for sub in subscriptions:
        for due_date in wanted[sub.id]:
            payment = existing.get((sub.id, due_date))
            if payment is None:
                continue

            candidates = _candidate_transactions(transactions_by_date, due_date)
            matching_tx = _best_match(sub, due_date, candidates, used_transaction_ids)

            if matching_tx:
                used_transaction_ids.add(matching_tx.id)
                payment.status = SubscriptionStatus.PAID
                payment.paid_date = matching_tx.booked_at.date()
                payment.paid_amount = matching_tx.amount
                payment.matched_transaction = matching_tx
            elif due_date < today and payment.status == SubscriptionStatus.PENDING:
                payment.status = SubscriptionStatus.OVERDUE
            else:
                continue

            to_update.append(payment)

    if to_update:
        SubscriptionPayment.objects.bulk_update(
            to_update, ["status", "paid_date", "paid_amount", "matched_transaction"]
        )


# Previdencia privada na Pluggy e `type: "SECURITY"`, com `subtype` em
# RETIREMENT | PGBL | VGBL. Nao existe `type: "PENSION"` no enum -- os tipos sao
# FIXED_INCOME, SECURITY, MUTUAL_FUND, EQUITY, ETF e COE.
# Ver https://docs.pluggy.ai/docs/investments
PENSION_INVESTMENT_TYPE = "SECURITY"
PENSION_INVESTMENT_SUBTYPES = frozenset({"RETIREMENT", "PGBL", "VGBL"})


def _is_pension_investment(investment_data: dict) -> bool:
    if (investment_data.get("type") or "").upper() == PENSION_INVESTMENT_TYPE:
        return True
    # `subtype` e opcional na Pluggy e `type` e obrigatorio, entao o type e o sinal
    # confiavel. O subtype fica como rede para provedor que rotula fora do padrao.
    return (investment_data.get("subtype") or "").upper() in PENSION_INVESTMENT_SUBTYPES


# `status` documentado: ACTIVE (comprado), PENDING (validando), TOTAL_WITHDRAWAL
# (vendido ou transferido).
WITHDRAWN_INVESTMENT_STATUS = "TOTAL_WITHDRAWAL"


def _is_withdrawn_investment(investment_data: dict) -> bool:
    """Posicao liquidada: a Pluggy diz que o ativo saiu da carteira.

    Sem checar isto, a lista de investimentos acumula linhas zeradas -- o sync
    gravava toda posicao devolvida, inclusive as ja vendidas.
    """
    return (investment_data.get("status") or "").upper() == WITHDRAWN_INVESTMENT_STATUS


def _pension_provider(investment_data: dict, connection) -> str:
    """Quem administra a previdencia.

    Nao existe campo `provider` no payload -- o codigo antigo lia esse nome e
    gravava string vazia sempre. A seguradora e o dado mais preciso (e nem sempre e
    a corretora pela qual foi contratada); a doc a mostra dentro de `institution` e
    tambem lista em `metadata`, entao os dois lugares sao consultados.
    """
    institution = investment_data.get("institution") or {}
    metadata = investment_data.get("metadata") or {}
    for source in (institution.get("insurer"), metadata.get("insurer")):
        if isinstance(source, dict) and source.get("name"):
            return source["name"]
    return institution.get("name") or connection.institution.name


def _sync_pension_plans(client, connection) -> None:
    """Grava as previdencias privadas do item.

    `client` fica sem anotacao de tipo de proposito: a unica coisa usada aqui e
    `fetch_item_investments`, e o teste passa o `FakePluggyClient` do conftest, que
    implementa a interface sem herdar de `PluggyClient`. Anotar a classe concreta
    seria afirmar algo que o chamador de teste nao cumpre.
    """
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
        if not _is_pension_investment(investment_data):
            continue
        PensionPlan.objects.update_or_create(
            connection=connection,
            external_id=investment_data["id"],
            defaults={
                "user": connection.user,
                "name": investment_data.get("name", "Previdência"),
                "provider": _pension_provider(investment_data, connection),
                "balance": investment_data.get("balance", 0) or 0,
                "annual_rate": investment_data.get("annualRate"),
                "amount_profit": investment_data.get("amountProfit"),
                "amount_original": investment_data.get("amountOriginal"),
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

        try:
            identity_data = client.fetch_item_identity(connection.external_id)
            if identity_data:
                _upsert_identity(connection, identity_data)
        except Exception as exc:
            logger.warning(
                "Error fetching identity for connection %s: %s",
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
            bank_data = item.get("bankData") or {}
            account, _ = Account.objects.update_or_create(
                external_id=item["id"],
                defaults={
                    "connection": connection,
                    "name": item.get("name", "Conta"),
                    "number": bank_data.get("transferNumber", ""),
                    "type": _normalize_account_type(item.get("type"), item.get("subtype")),
                    "currency": item.get("currencyCode", "BRL"),
                    "balance": item.get("balance", 0) or 0,
                    "available_balance": item.get("availableBalance", item.get("balance", 0)) or 0,
                    # Campos crus da Pluggy sem uso na tela hoje -- ver comentario
                    # em `Account` (models.py) sobre o uso pelo relatorio de IA.
                    "subtype": item.get("subtype") or "",
                    "marketing_name": item.get("marketingName") or "",
                    "owner_name": item.get("owner") or "",
                    "tax_number": item.get("taxNumber") or "",
                    "closing_balance": bank_data.get("closingBalance"),
                    "overdraft_limit": bank_data.get("overdraftContractedLimit"),
                    "overdraft_used": bank_data.get("overdraftUsedLimit"),
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
                        # Campos crus da Pluggy sem uso na tela hoje -- ver
                        # comentario em `Card` (models.py) sobre o uso pelo
                        # relatorio de IA.
                        "brand": credit_data.get("brand") or "",
                        "level": credit_data.get("level") or "",
                        "available_credit_limit": credit_data.get("availableCreditLimit"),
                        "minimum_payment": credit_data.get("minimumPayment"),
                        "is_limit_flexible": credit_data.get("isLimitFlexible"),
                        "status": credit_data.get("status") or "",
                        "holder_type": credit_data.get("holderType") or "",
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
                # Previdencia sai daqui e entra como PensionPlan. Gravar nos dois
                # somaria o mesmo ativo duas vezes no patrimonio:
                # `InvestmentPosition.market_value` + `PensionPlan.balance`.
                if _is_pension_investment(investment_data):
                    continue

                if _is_withdrawn_investment(investment_data):
                    # Remove em vez de so pular: a Pluggy esta dizendo que o ativo
                    # saiu da carteira, e pular deixaria a linha antiga para sempre.
                    # O historico agregado de patrimonio vive em NetWorthSnapshot,
                    # nao aqui.
                    deleted, _ = Investment.objects.filter(
                        connection=connection, external_id=investment_data["id"]
                    ).delete()
                    if deleted:
                        logger.info(
                            "Investimento liquidado removido: %s (%s)",
                            investment_data.get("name"),
                            investment_data["id"],
                        )
                    continue

                investment, _ = Investment.objects.update_or_create(
                    external_id=investment_data["id"],
                    defaults={
                        "connection": connection,
                        "name": investment_data.get("name", "Investimento"),
                        "kind": investment_data.get("type", "other"),
                        "currency": investment_data.get("currencyCode", "BRL"),
                        # Campos crus da Pluggy sem uso na tela hoje -- ver
                        # comentario em `Investment` (models.py) sobre o uso pelo
                        # relatorio de IA.
                        "subtype": investment_data.get("subtype") or "",
                        "number": investment_data.get("number") or "",
                        "isin": investment_data.get("isin") or "",
                        "code": investment_data.get("code") or "",
                        "issuer": investment_data.get("issuer") or "",
                        "issuer_cnpj": investment_data.get("issuerCNPJ") or "",
                        "issue_date": _parse_date_only(investment_data.get("issueDate")),
                        "due_date": _parse_date_only(investment_data.get("dueDate")),
                        "rate_type": investment_data.get("rateType") or "",
                        "tax_exempt": investment_data.get("taxExempt"),
                        "rate_periodicity": investment_data.get("ratePeriodicity") or "",
                        "indexer_additional_info": (
                            investment_data.get("indexerAdditionalInfo") or ""
                        ),
                    },
                )
                InvestmentPosition.objects.update_or_create(
                    investment=investment,
                    as_of_date=today,
                    defaults={
                        "quantity": investment_data.get("quantity", 0) or 0,
                        # `value` e o valor da cota. O campo lido antes (`price`)
                        # nao existe no payload, entao unit_price era sempre zero.
                        "unit_price": investment_data.get("value", 0) or 0,
                        "market_value": investment_data.get("balance", 0) or 0,
                        # Rentabilidade/estado do dia (campos crus da Pluggy) --
                        # ver comentario em `InvestmentPosition` (models.py).
                        "last_month_rate": investment_data.get("lastMonthRate"),
                        "last_twelve_months_rate": investment_data.get("lastTwelveMonthsRate"),
                        "annual_rate": investment_data.get("annualRate"),
                        "fixed_annual_rate": investment_data.get("fixedAnnualRate"),
                        "rate": investment_data.get("rate"),
                        "amount_profit": investment_data.get("amountProfit"),
                        "amount_withdrawal": investment_data.get("amountWithdrawal"),
                        "amount_original": investment_data.get("amountOriginal"),
                        "price_factor": investment_data.get("priceFactor"),
                        "status": investment_data.get("status") or "",
                        "purchase_date": _parse_date_only(investment_data.get("purchaseDate")),
                        "grace_period_date": _parse_date_only(
                            investment_data.get("gracePeriodDate")
                        ),
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


@shared_task
def snapshot_all_users() -> int:
    """Grava o snapshot patrimonial diario de todo usuario com conexao.

    Roda no beat porque a Pluggy so avisa quando ha movimento: sem isto um mes
    sem sync deixa buraco no grafico de evolucao patrimonial. Usuario sem
    conexao fica de fora -- um snapshot zerado por dia seria ruido.
    """
    users = get_user_model().objects.filter(connections__isnull=False).distinct()
    written = 0
    for user in users:
        # Um usuario com dado ruim nao pode abortar o lote: a task roda uma vez
        # por dia e nao existe retry por usuario.
        try:
            snapshot_net_worth(user)
            written += 1
        except Exception:
            logger.exception("Snapshot patrimonial falhou para o usuario %s", user.pk)
    logger.info("Snapshot patrimonial gravado para %s de %s usuarios", written, users.count())
    return written


@shared_task
def reconcile_all_subscriptions() -> int:
    """Reconcilia assinaturas de todo usuario com assinatura ativa.

    Sem isto uma assinatura vencida so virava `overdue` no proximo sync, e
    contas pagas fora de instituicao conectada nunca ganhavam a linha do mes.
    """
    users = get_user_model().objects.filter(subscriptions__is_active=True).distinct()
    reconciled = 0
    for user in users:
        try:
            _reconcile_subscriptions(user)
            reconciled += 1
        except Exception:
            logger.exception("Reconciliacao de assinaturas falhou para o usuario %s", user.pk)
    logger.info("Assinaturas reconciliadas para %s de %s usuarios", reconciled, users.count())
    return reconciled


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
