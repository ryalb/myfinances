"""Testes de _reconcile_subscriptions.

A funcao foi reescrita para resolver a janela em um numero fixo de queries
(antes era uma query por par (assinatura, mes), dentro de cada sync).
Estes testes travam o comportamento observavel e o custo em queries.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finance.models import (
    Account,
    AccountType,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
    Transaction,
    TransactionType,
)
from apps.finance.tasks import _due_date_for, _reconcile_subscriptions

SUBSCRIPTIONS_URL = "/api/v1/subscriptions/"


def _booked_at(day):
    return timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))


def _previous_month_due_date(due_day):
    last_day_of_previous_month = timezone.localdate().replace(day=1) - timedelta(days=1)
    return _due_date_for(
        last_day_of_previous_month.year, last_day_of_previous_month.month, due_day
    )


@pytest.fixture
def subscription(db, user, connection):
    return Subscription.objects.create(
        user=user,
        connection=connection,
        name="Netflix",
        category=SubscriptionCategory.STREAMING,
        amount=55,
        due_day=10,
    )


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_creates_one_payment_per_month_in_the_window(subscription, user):
    _reconcile_subscriptions(user)

    # janela de -3 a +6 meses = 10 meses
    assert SubscriptionPayment.objects.filter(subscription=subscription).count() == 10


@pytest.mark.django_db
def test_is_idempotent_across_runs(subscription, user):
    _reconcile_subscriptions(user)
    _reconcile_subscriptions(user)

    assert SubscriptionPayment.objects.filter(subscription=subscription).count() == 10


@pytest.mark.django_db
def test_months_back_extends_the_backfill_window(subscription, user, account):
    """Uma assinatura recem-cadastrada usa `months_back` maior para casar com
    transacoes antigas que a janela padrao (-3 meses) nunca alcancaria."""
    today = timezone.localdate()
    old_due_date = _due_date_for(today.year, today.month, subscription.due_day) - timedelta(
        days=300
    )
    Transaction.objects.create(
        account=account,
        external_id="tx-netflix-antiga",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(old_due_date),
    )

    _reconcile_subscriptions(user, months_back=12)

    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=old_due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.matched_transaction_id is not None


@pytest.mark.django_db
def test_marks_past_due_pending_payment_as_overdue(subscription, user):
    _reconcile_subscriptions(user)

    today = timezone.localdate()
    past = SubscriptionPayment.objects.filter(subscription=subscription, due_date__lt=today)
    assert past.exists()
    assert all(p.status == SubscriptionStatus.OVERDUE for p in past)


@pytest.mark.django_db
def test_matches_transaction_by_name_and_marks_paid(subscription, user, account):
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, subscription.due_day)

    tx = Transaction.objects.create(
        account=account,
        external_id="tx-netflix",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=timezone.make_aware(
            timezone.datetime.combine(due_date, timezone.datetime.min.time())
        ),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.paid_date == due_date
    assert payment.paid_amount == tx.amount


@pytest.mark.django_db
def test_matches_transaction_when_description_omits_a_space(user, connection, account):
    """O banco as vezes junta duas palavras do nome do comerciante -- "Google
    Youtube Premium" cadastrado pelo usuario chega como "Google Youtubepremium"
    na transacao (sem o espaco). String crua nunca casava por essa diferenca, e
    a categoria tambem nao ajuda (a assinatura usa "streaming", o extrato vem
    com "Internet" ou "Servicos digitais")."""
    sub = Subscription.objects.create(
        user=user,
        connection=connection,
        name="Google Youtube Premium",
        category=SubscriptionCategory.STREAMING,
        amount="53.90",
        due_day=20,
    )
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, sub.due_day)

    tx = Transaction.objects.create(
        account=account,
        external_id="tx-youtube-premium",
        description="Google Youtubepremium",
        category="Internet",
        amount="53.90",
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=sub, due_date=due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.matched_transaction_id == tx.id


@pytest.mark.django_db
def test_ignores_transactions_from_other_users(subscription, user, other_user):
    """A busca de transacoes precisa continuar escopada ao usuario."""
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, subscription.due_day)

    from apps.finance.models import (
        Account,
        AccountType,
        Connection,
        ConnectionStatus,
        FinancialInstitution,
    )

    other_institution = FinancialInstitution.objects.create(name="Outro", provider_id="777")
    other_connection = Connection.objects.create(
        user=other_user,
        institution=other_institution,
        external_id="item-outro-sub",
        status=ConnectionStatus.ACTIVE,
    )
    other_account = Account.objects.create(
        connection=other_connection,
        external_id="acc-outro-sub",
        name="Conta do outro",
        type=AccountType.CHECKING,
    )
    Transaction.objects.create(
        account=other_account,
        external_id="tx-netflix-outro",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=timezone.make_aware(
            timezone.datetime.combine(due_date, timezone.datetime.min.time())
        ),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=due_date)
    assert payment.status != SubscriptionStatus.PAID, "casou com transacao de outro usuario"


@pytest.mark.django_db
def test_skips_inactive_subscriptions(user, connection):
    Subscription.objects.create(
        user=user,
        connection=connection,
        name="Cancelada",
        category=SubscriptionCategory.OTHER,
        amount=10,
        due_day=5,
        is_active=False,
    )

    _reconcile_subscriptions(user)

    assert SubscriptionPayment.objects.count() == 0


@pytest.mark.django_db
def test_query_count_does_not_grow_with_subscriptions(user, connection):
    """Antes: ~30 queries por assinatura (uma por par assinatura/mes).
    Agora o custo e fixo: nao depende de quantas assinaturas existem."""
    from django.db import connection as db_connection
    from django.test.utils import CaptureQueriesContext

    def count_queries_for(n_subs: int) -> int:
        Subscription.objects.filter(user=user).delete()
        for i in range(n_subs):
            Subscription.objects.create(
                user=user,
                connection=connection,
                name=f"Servico {i}",
                category=SubscriptionCategory.OTHER,
                amount=10 + i,
                due_day=(i % 28) + 1,
            )
        with CaptureQueriesContext(db_connection) as ctx:
            _reconcile_subscriptions(user)
        return len(ctx)

    with_10 = count_queries_for(10)
    with_40 = count_queries_for(40)

    assert with_10 == with_40, f"custo cresceu com o numero de assinaturas: {with_10} -> {with_40}"
    assert with_10 <= 8, f"esperava custo fixo pequeno, foram {with_10} queries"


@pytest.mark.django_db
def test_clamps_due_day_to_short_months():
    assert _due_date_for(2026, 2, 31).day == 28
    assert _due_date_for(2026, 4, 31).day == 30
    assert _due_date_for(2026, 1, 31).day == 31


@pytest.mark.django_db
def test_matches_transaction_within_tolerance_window(subscription, user, account):
    """Debito real raramente cai exatamente no dia calculado -- por isso existe
    uma janela de tolerancia em vez de exigir o dia exato."""
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, subscription.due_day)

    tx = Transaction.objects.create(
        account=account,
        external_id="tx-netflix-atraso",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date + timedelta(days=3)),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.paid_date == due_date + timedelta(days=3)
    assert payment.matched_transaction_id == tx.id


@pytest.mark.django_db
def test_does_not_match_transaction_outside_tolerance_window(subscription, user, account):
    due_date = _previous_month_due_date(subscription.due_day)

    Transaction.objects.create(
        account=account,
        external_id="tx-netflix-longe",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date + timedelta(days=10)),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=due_date)
    assert payment.status == SubscriptionStatus.OVERDUE
    assert payment.matched_transaction_id is None


@pytest.mark.django_db
def test_scopes_match_to_payment_account_when_set(user, connection, account):
    other_account = Account.objects.create(
        connection=connection,
        external_id="acc-2",
        name="Conta Poupança",
        type=AccountType.SAVINGS,
    )
    sub = Subscription.objects.create(
        user=user,
        connection=connection,
        name="Netflix",
        category=SubscriptionCategory.STREAMING,
        amount=55,
        due_day=10,
        payment_account=account,
    )
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, sub.due_day)

    Transaction.objects.create(
        account=other_account,
        external_id="tx-conta-errada",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date),
    )
    tx_right_account = Transaction.objects.create(
        account=account,
        external_id="tx-conta-certa",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date + timedelta(days=1)),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=sub, due_date=due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.matched_transaction_id == tx_right_account.id


@pytest.mark.django_db
def test_matches_card_transaction_even_when_payment_account_is_set(user, connection, account):
    """`payment_account` referencia Account, nunca Card. Uma assinatura paga no
    cartao (ex.: escolhida so por costume, sem reflexo em qual instrumento cobra)
    nao pode ficar sem match so porque tem uma conta de referencia cadastrada."""
    from apps.finance.models import Card

    card = Card.objects.create(connection=connection, external_id="card-1", name="Cartão")
    sub = Subscription.objects.create(
        user=user,
        connection=connection,
        name="Claro Flex",
        category=SubscriptionCategory.PHONE,
        amount=44.90,
        due_day=8,
        payment_account=account,
    )
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, sub.due_day)

    tx = Transaction.objects.create(
        card=card,
        external_id="tx-claro-flex-cartao",
        description="Claro Flex",
        amount=44.90,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date),
    )

    _reconcile_subscriptions(user)

    payment = SubscriptionPayment.objects.get(subscription=sub, due_date=due_date)
    assert payment.status == SubscriptionStatus.PAID
    assert payment.matched_transaction_id == tx.id


@pytest.mark.django_db
def test_matches_when_subscription_name_has_disambiguating_suffix(user, connection, account):
    """Usuario apelida duas linhas da mesma operadora ("Claro Flex - Ryan",
    "Claro Flex - Sheyla") para distingui-las, mas o banco manda as duas com a
    mesma descricao "Claro Flex" -- o sufixo nao pode impedir o match."""
    sub_ryan = Subscription.objects.create(
        user=user, connection=connection, name="Claro Flex - Ryan",
        category=SubscriptionCategory.PHONE, amount="44.90", due_day=8,
    )
    sub_sheyla = Subscription.objects.create(
        user=user, connection=connection, name="Claro Flex - Sheyla",
        category=SubscriptionCategory.PHONE, amount="39.99", due_day=30,
    )
    today = timezone.localdate()
    due_date_ryan = _due_date_for(today.year, today.month, sub_ryan.due_day)
    due_date_sheyla = _due_date_for(today.year, today.month, sub_sheyla.due_day)

    tx_ryan = Transaction.objects.create(
        account=account,
        external_id="tx-claro-flex-ryan",
        description="Claro Flex",
        amount="44.90",
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date_ryan),
    )
    tx_sheyla = Transaction.objects.create(
        account=account,
        external_id="tx-claro-flex-sheyla",
        description="Claro Flex",
        amount="39.99",
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date_sheyla),
    )

    _reconcile_subscriptions(user)

    payment_ryan = SubscriptionPayment.objects.get(subscription=sub_ryan, due_date=due_date_ryan)
    payment_sheyla = SubscriptionPayment.objects.get(
        subscription=sub_sheyla, due_date=due_date_sheyla
    )
    assert payment_ryan.status == SubscriptionStatus.PAID
    assert payment_ryan.matched_transaction_id == tx_ryan.id
    assert payment_sheyla.status == SubscriptionStatus.PAID
    assert payment_sheyla.matched_transaction_id == tx_sheyla.id


@pytest.mark.django_db
def test_does_not_double_claim_the_same_transaction(user, connection, account):
    """Janela mais larga aumenta a chance de duas assinaturas com nome/categoria
    parecidos colidirem no mesmo debito -- uma transacao serve para um pagamento."""
    sub_a = Subscription.objects.create(
        user=user, connection=connection, name="Streaming A",
        category=SubscriptionCategory.STREAMING, amount=30, due_day=10,
    )
    sub_b = Subscription.objects.create(
        user=user, connection=connection, name="Streaming B",
        category=SubscriptionCategory.STREAMING, amount=30, due_day=10,
    )
    today = timezone.localdate()
    due_date = _due_date_for(today.year, today.month, 10)

    Transaction.objects.create(
        account=account,
        external_id="tx-streaming-unico",
        description="Cobranca streaming",
        category=SubscriptionCategory.STREAMING,
        amount=30,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date),
    )

    _reconcile_subscriptions(user)

    payments = SubscriptionPayment.objects.filter(
        subscription__in=[sub_a, sub_b], due_date=due_date
    )
    paid = [p for p in payments if p.status == SubscriptionStatus.PAID]
    assert len(paid) == 1, "a mesma transacao nao pode pagar as duas assinaturas"


@pytest.mark.django_db
def test_overdue_payment_becomes_paid_when_late_transaction_appears(subscription, user, account):
    """Uma vez overdue, o pagamento so volta a paid se uma transacao aparecer
    dentro da janela num sync seguinte -- a reconciliacao roda a cada sync."""
    due_date = _previous_month_due_date(subscription.due_day)

    _reconcile_subscriptions(user)
    payment = SubscriptionPayment.objects.get(subscription=subscription, due_date=due_date)
    assert payment.status == SubscriptionStatus.OVERDUE

    tx = Transaction.objects.create(
        account=account,
        external_id="tx-netflix-atrasada",
        description="Pagamento NETFLIX mensal",
        amount=55,
        type=TransactionType.DEBIT,
        booked_at=_booked_at(due_date + timedelta(days=4)),
    )

    _reconcile_subscriptions(user)

    payment.refresh_from_db()
    assert payment.status == SubscriptionStatus.PAID
    assert payment.matched_transaction_id == tx.id


@pytest.mark.django_db
def test_creating_a_subscription_via_api_backfills_matching_history(api, user, account):
    """Sem reconciliar na criacao, a assinatura so ganhava historico no proximo
    sync Pluggy ou no beat diario -- o usuario cadastra e ve "sem historico"
    mesmo com meses de cobrancas que ja deveriam casar (ex.: Spotify cobrado
    todo mes ha quase um ano antes do usuario cadastrar a assinatura)."""
    today = timezone.localdate()
    old_due_date = _due_date_for(today.year, today.month, 11) - timedelta(days=180)
    Transaction.objects.create(
        account=account,
        external_id="tx-spotify-antiga",
        description="Dm*Spotify",
        amount="40.90",
        type=TransactionType.DEBIT,
        booked_at=_booked_at(old_due_date),
    )

    response = api.post(
        SUBSCRIPTIONS_URL,
        {"name": "Spotify", "category": "streaming", "amount": "40.90", "due_day": 11},
        format="json",
    )

    assert response.status_code == 201, response.data
    payment = SubscriptionPayment.objects.get(
        subscription_id=response.data["id"], due_date=old_due_date
    )
    assert payment.status == SubscriptionStatus.PAID
    assert payment.matched_transaction_id is not None
