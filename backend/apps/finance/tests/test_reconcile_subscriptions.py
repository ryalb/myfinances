"""Testes de _reconcile_subscriptions.

A funcao foi reescrita para resolver a janela em um numero fixo de queries
(antes era uma query por par (assinatura, mes), dentro de cada sync).
Estes testes travam o comportamento observavel e o custo em queries.
"""

import pytest
from django.utils import timezone

from apps.finance.models import (
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
    Transaction,
    TransactionType,
)
from apps.finance.tasks import _due_date_for, _reconcile_subscriptions


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
