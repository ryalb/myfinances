"""Testes das tasks periodicas (Celery beat).

Antes disto nada rodava sozinho: `recompute_user_snapshot` e
`_reconcile_subscriptions` so disparavam dentro de um sync (webhook da Pluggy ou
acao manual). Consequencia observavel: um mes sem sync deixava buraco no grafico
de evolucao patrimonial, e uma assinatura vencida nunca virava `overdue`.
"""

import pytest
from django.conf import settings
from django.utils import timezone

from apps.finance.models import (
    Connection,
    ConnectionStatus,
    NetWorthSnapshot,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
)
from apps.finance.tasks import reconcile_all_subscriptions, snapshot_all_users


def test_beat_schedule_registers_both_periodic_tasks():
    scheduled = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}

    assert "apps.finance.tasks.snapshot_all_users" in scheduled
    assert "apps.finance.tasks.reconcile_all_subscriptions" in scheduled


@pytest.mark.django_db
def test_snapshot_all_users_creates_one_snapshot_per_connected_user(user, connection, account):
    snapshot_all_users()

    snapshot = NetWorthSnapshot.objects.get(user=user)
    assert snapshot.date == timezone.localdate()
    assert snapshot.assets > 0


@pytest.mark.django_db
def test_snapshot_all_users_is_idempotent_within_the_same_day(user, connection, account):
    snapshot_all_users()
    snapshot_all_users()

    assert NetWorthSnapshot.objects.filter(user=user, date=timezone.localdate()).count() == 1


@pytest.mark.django_db
def test_snapshot_all_users_skips_users_without_connections(user, other_user, connection, account):
    """Sem conexao nao ha patrimonio a consolidar; um snapshot zerado por dia
    seria ruido no grafico."""
    snapshot_all_users()

    assert NetWorthSnapshot.objects.filter(user=user).exists()
    assert not NetWorthSnapshot.objects.filter(user=other_user).exists()


@pytest.mark.django_db
def test_snapshot_all_users_continues_after_a_failing_user(
    user, other_user, institution, connection, account, monkeypatch
):
    """Um usuario com dado ruim nao pode impedir o snapshot dos demais: a task
    roda uma vez por dia e nao ha retry por usuario."""
    Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-outro-snap",
        status=ConnectionStatus.ACTIVE,
    )

    from apps.finance import tasks

    original = tasks.snapshot_net_worth

    def explode_for_first_user(target_user, *args, **kwargs):
        if target_user.pk == user.pk:
            raise ValueError("dado corrompido")
        return original(target_user, *args, **kwargs)

    monkeypatch.setattr(tasks, "snapshot_net_worth", explode_for_first_user)

    snapshot_all_users()

    assert not NetWorthSnapshot.objects.filter(user=user).exists()
    assert NetWorthSnapshot.objects.filter(
        user=other_user
    ).exists(), "a falha do primeiro usuario abortou o restante do lote"


@pytest.mark.django_db
def test_reconcile_all_subscriptions_marks_overdue_without_a_sync(user):
    subscription = Subscription.objects.create(
        user=user,
        name="Conta de agua",
        category=SubscriptionCategory.UTILITIES,
        amount=90,
        due_day=10,
    )

    reconcile_all_subscriptions()

    past = SubscriptionPayment.objects.filter(
        subscription=subscription, due_date__lt=timezone.localdate()
    )
    assert past.exists()
    assert all(payment.status == SubscriptionStatus.OVERDUE for payment in past)


@pytest.mark.django_db
def test_reconcile_all_subscriptions_skips_users_without_active_subscriptions(user, other_user):
    Subscription.objects.create(
        user=other_user,
        name="Cancelada",
        category=SubscriptionCategory.OTHER,
        amount=10,
        due_day=5,
        is_active=False,
    )

    reconcile_all_subscriptions()

    assert SubscriptionPayment.objects.count() == 0


@pytest.mark.django_db
def test_reconcile_all_subscriptions_continues_after_a_failing_user(user, other_user, monkeypatch):
    for target in (user, other_user):
        Subscription.objects.create(
            user=target,
            name=f"Internet {target.pk}",
            category=SubscriptionCategory.INTERNET,
            amount=120,
            due_day=8,
        )

    from apps.finance import tasks

    original = tasks._reconcile_subscriptions

    def explode_for_first_user(target_user):
        if target_user.pk == user.pk:
            raise ValueError("dado corrompido")
        return original(target_user)

    monkeypatch.setattr(tasks, "_reconcile_subscriptions", explode_for_first_user)

    reconcile_all_subscriptions()

    assert not SubscriptionPayment.objects.filter(subscription__user=user).exists()
    assert SubscriptionPayment.objects.filter(
        subscription__user=other_user
    ).exists(), "a falha do primeiro usuario abortou o restante do lote"
