"""Testes dos alertas in-app.

Alertas sao derivados do estado atual, nao registros persistidos. A escolha e
deliberada: um alerta derivado desaparece quando a condicao se resolve (pagamento
marcado como pago, conexao reconectada), enquanto uma tabela de notificacoes
precisaria de marcacao de lido, expiracao e limpeza -- e ainda assim mostraria
alerta de problema que ja passou.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.finance.alerts import (
    ALERT_SEVERITY_ORDER,
    STALE_SYNC_DAYS,
    UPCOMING_ALERT_DAYS,
    _budget_bucket_alerts,
    build_user_alerts,
)
from apps.finance.models import (
    Account,
    AccountType,
    BudgetBucket,
    BudgetBucketTarget,
    Connection,
    ConnectionStatus,
    FinanceTag,
    FinanceTagKind,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
    Transaction,
    TransactionType,
)


@pytest.fixture
def active_connection(db, user, institution):
    return Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-alertas",
        status=ConnectionStatus.ACTIVE,
        last_synced_at=timezone.now(),
    )


def kinds(alerts) -> list[str]:
    return [alert["kind"] for alert in alerts]


@pytest.mark.django_db
def test_no_data_produces_no_alerts(user):
    assert build_user_alerts(user) == []


@pytest.mark.django_db
def test_overdue_subscription_becomes_a_danger_alert(user, active_connection):
    subscription = Subscription.objects.create(
        user=user,
        name="Conta de agua",
        category=SubscriptionCategory.UTILITIES,
        amount=Decimal("90.00"),
        due_day=10,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date=timezone.localdate() - timedelta(days=5),
        status=SubscriptionStatus.OVERDUE,
    )

    alerts = build_user_alerts(user)

    assert "subscription_overdue" in kinds(alerts)
    overdue = next(a for a in alerts if a["kind"] == "subscription_overdue")
    assert overdue["severity"] == "danger"
    assert "Conta de agua" in overdue["detail"]
    assert overdue["action_path"] == "/subscriptions"


@pytest.mark.django_db
def test_upcoming_subscription_becomes_an_info_alert(user, active_connection):
    subscription = Subscription.objects.create(
        user=user,
        name="Internet",
        category=SubscriptionCategory.INTERNET,
        amount=Decimal("120.00"),
        due_day=10,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date=timezone.localdate() + timedelta(days=2),
        status=SubscriptionStatus.PENDING,
    )

    alerts = build_user_alerts(user)

    upcoming = next(a for a in alerts if a["kind"] == "subscription_due_soon")
    assert upcoming["severity"] == "info"
    assert "Internet" in upcoming["detail"]


@pytest.mark.django_db
def test_upcoming_beyond_the_alert_window_is_not_reported(user, active_connection):
    """A visao de assinaturas mostra 30 dias; alerta de 30 dias vira ruido
    permanente, porque sempre existe algo vencendo no mes."""
    subscription = Subscription.objects.create(
        user=user,
        name="Internet",
        category=SubscriptionCategory.INTERNET,
        amount=Decimal("120.00"),
        due_day=10,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date=timezone.localdate() + timedelta(days=UPCOMING_ALERT_DAYS + 5),
        status=SubscriptionStatus.PENDING,
    )

    assert "subscription_due_soon" not in kinds(build_user_alerts(user))


@pytest.mark.django_db
def test_connection_in_error_becomes_a_danger_alert(user, institution):
    Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-quebrado",
        status=ConnectionStatus.ERROR,
        error_message="credenciais invalidas",
        last_synced_at=timezone.now(),
    )

    alerts = build_user_alerts(user)

    broken = next(a for a in alerts if a["kind"] == "connection_error")
    assert broken["severity"] == "danger"
    assert institution.name in broken["detail"]
    assert broken["action_path"] == "/integrations"


@pytest.mark.django_db
def test_stale_sync_becomes_a_warning(user, institution):
    """A Pluggy sincroniza sozinha a cada 24h no maximo. Passar dias sem sync
    significa dado velho no dashboard, sem nada na tela dizendo isso."""
    Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-parado",
        status=ConnectionStatus.ACTIVE,
        last_synced_at=timezone.now() - timedelta(days=STALE_SYNC_DAYS + 1),
    )

    alerts = build_user_alerts(user)

    stale = next(a for a in alerts if a["kind"] == "sync_stale")
    assert stale["severity"] == "warning"
    assert institution.name in stale["detail"]


@pytest.mark.django_db
def test_recent_sync_does_not_warn(user, active_connection):
    assert "sync_stale" not in kinds(build_user_alerts(user))


@pytest.mark.django_db
def test_never_synced_active_connection_warns(user, institution):
    Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-nunca",
        status=ConnectionStatus.ACTIVE,
        last_synced_at=None,
    )

    assert "sync_stale" in kinds(build_user_alerts(user))


@pytest.mark.django_db
def test_pending_connection_does_not_warn_about_staleness(user, institution):
    """Conexao recem-criada ainda nao sincronizou por definicao."""
    Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-pendente",
        status=ConnectionStatus.PENDING,
        last_synced_at=None,
    )

    assert "sync_stale" not in kinds(build_user_alerts(user))


@pytest.mark.django_db
def test_alerts_are_ordered_worst_first(user, institution):
    """O contador no cabecalho mostra os primeiros: se um aviso informativo vier
    antes de uma conexao quebrada, o usuario ve o menos importante."""
    Connection.objects.create(
        user=user,
        institution=institution,
        external_id="item-parado-2",
        status=ConnectionStatus.ACTIVE,
        last_synced_at=timezone.now() - timedelta(days=STALE_SYNC_DAYS + 1),
    )
    broken_institution = institution.__class__.objects.create(
        name="Banco quebrado", provider_id="555"
    )
    Connection.objects.create(
        user=user,
        institution=broken_institution,
        external_id="item-quebrado-2",
        status=ConnectionStatus.ERROR,
        error_message="erro",
        last_synced_at=timezone.now(),
    )
    subscription = Subscription.objects.create(
        user=user,
        name="Internet",
        category=SubscriptionCategory.INTERNET,
        amount=Decimal("120.00"),
        due_day=10,
    )
    SubscriptionPayment.objects.create(
        subscription=subscription,
        due_date=timezone.localdate() + timedelta(days=2),
        status=SubscriptionStatus.PENDING,
    )

    severities = [alert["severity"] for alert in build_user_alerts(user)]
    ranks = [ALERT_SEVERITY_ORDER.index(s) for s in severities]

    assert ranks == sorted(ranks), f"ordem fora de gravidade: {severities}"


@pytest.mark.django_db
def test_alerts_never_cross_users(user, other_user, institution):
    Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-do-outro-alerta",
        status=ConnectionStatus.ERROR,
        error_message="erro do outro",
        last_synced_at=timezone.now(),
    )

    assert build_user_alerts(user) == []


@pytest.mark.django_db
def test_cost_does_not_grow_with_the_number_of_connections(user, institution):
    from django.db import connection as db_connection
    from django.test.utils import CaptureQueriesContext

    def count_queries_for(n: int) -> int:
        Connection.objects.filter(user=user).delete()
        for i in range(n):
            Connection.objects.create(
                user=user,
                institution=institution,
                external_id=f"item-custo-{i}",
                status=ConnectionStatus.ACTIVE,
                last_synced_at=timezone.now() - timedelta(days=STALE_SYNC_DAYS + 1),
            )
        with CaptureQueriesContext(db_connection) as ctx:
            build_user_alerts(user)
        return len(ctx)

    with_3 = count_queries_for(3)
    with_20 = count_queries_for(20)

    assert with_3 == with_20, f"custo cresceu com as conexoes: {with_3} -> {with_20}"


# --------------------------------------------------------------------------
# _budget_bucket_alerts (Fase 6: otimizador)
# --------------------------------------------------------------------------


def _income_tx(account, *, external_id, amount, booked_at):
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description="renda",
        amount=Decimal(amount),
        type=TransactionType.CREDIT,
        category="Salário",
        booked_at=timezone.make_aware(timezone.datetime(*booked_at)),
    )


def _credit_tx(account, *, external_id, amount, booked_at):
    return Transaction.objects.create(
        account=account,
        external_id=external_id,
        description="aporte",
        amount=Decimal(amount),
        type=TransactionType.CREDIT,
        booked_at=timezone.make_aware(timezone.datetime(*booked_at)),
    )


REFERENCE_TODAY = date(2026, 8, 15)


@pytest.mark.django_db
def test_no_target_defined_skips_the_check_entirely(user):
    assert _budget_bucket_alerts(user, today=REFERENCE_TODAY) == []


@pytest.mark.django_db
def test_bucket_under_target_two_months_in_a_row_alerts(user, account):
    BudgetBucketTarget.objects.create(
        user=user, bucket=BudgetBucket.INVESTMENTS, target_percentage=Decimal("50")
    )
    _income_tx(account, external_id="tx-income-jun", amount="5000", booked_at=(2026, 6, 5))
    _income_tx(account, external_id="tx-income-jul", amount="5000", booked_at=(2026, 7, 5))
    # Nenhum credito em conta tagueada de investimentos em nenhum dos dois meses.

    alerts = _budget_bucket_alerts(user, today=REFERENCE_TODAY)

    assert len(alerts) == 1
    assert alerts[0]["kind"] == "budget_bucket_under_target"
    assert alerts[0]["severity"] == "warning"
    assert alerts[0]["action_path"] == "/optimizer"


@pytest.mark.django_db
def test_bucket_under_target_only_one_month_does_not_alert(user, account, connection):
    brokerage = Account.objects.create(
        connection=connection,
        external_id="acc-brok",
        name="Corretora",
        type=AccountType.BROKERAGE,
    )
    FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.BUDGET_BUCKET,
        value=BudgetBucket.INVESTMENTS,
        account=brokerage,
    )
    BudgetBucketTarget.objects.create(
        user=user, bucket=BudgetBucket.INVESTMENTS, target_percentage=Decimal("50")
    )
    _income_tx(account, external_id="tx-income-jun", amount="5000", booked_at=(2026, 6, 5))
    _income_tx(account, external_id="tx-income-jul", amount="5000", booked_at=(2026, 7, 5))
    # Junho bate o alvo (aporte de 50% da renda); julho fica sem aporte nenhum.
    _credit_tx(brokerage, external_id="tx-aporte-jun", amount="2500", booked_at=(2026, 6, 20))

    alerts = _budget_bucket_alerts(user, today=REFERENCE_TODAY)

    assert alerts == []


@pytest.mark.django_db
def test_bucket_on_target_never_alerts(user, account, connection):
    brokerage = Account.objects.create(
        connection=connection,
        external_id="acc-brok-2",
        name="Corretora",
        type=AccountType.BROKERAGE,
    )
    FinanceTag.objects.create(
        user=user,
        kind=FinanceTagKind.BUDGET_BUCKET,
        value=BudgetBucket.INVESTMENTS,
        account=brokerage,
    )
    BudgetBucketTarget.objects.create(
        user=user, bucket=BudgetBucket.INVESTMENTS, target_percentage=Decimal("50")
    )
    _income_tx(account, external_id="tx-income-jun", amount="5000", booked_at=(2026, 6, 5))
    _income_tx(account, external_id="tx-income-jul", amount="5000", booked_at=(2026, 7, 5))
    _credit_tx(brokerage, external_id="tx-aporte-jun", amount="2500", booked_at=(2026, 6, 20))
    _credit_tx(brokerage, external_id="tx-aporte-jul", amount="2500", booked_at=(2026, 7, 20))

    assert _budget_bucket_alerts(user, today=REFERENCE_TODAY) == []


@pytest.mark.django_db
def test_build_user_alerts_includes_budget_bucket_alerts(user, monkeypatch):
    """So confere a fiacao com `build_user_alerts` -- a logica do calculo em si
    ja e testada acima, direto em `_budget_bucket_alerts`."""
    canned = [
        {
            "kind": "budget_bucket_under_target",
            "severity": "warning",
            "title": "titulo",
            "detail": "detalhe",
            "action_path": "/optimizer",
        }
    ]
    monkeypatch.setattr("apps.finance.alerts._budget_bucket_alerts", lambda user, today: canned)

    assert "budget_bucket_under_target" in kinds(build_user_alerts(user))
