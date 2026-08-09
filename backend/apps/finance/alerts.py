"""Alertas in-app derivados do estado atual.

Nao ha model de notificacao de proposito. Um alerta derivado desaparece quando a
condicao se resolve -- pagamento marcado como pago, conexao reconectada -- enquanto
uma tabela precisaria de marcacao de lido, expiracao e limpeza, e ainda assim
mostraria alerta de problema que ja passou.

A entrega em tempo real vem de graca: `useRealtimeSync` no frontend chama
`refreshNuxtData()` a cada evento de sync, o que refaz a consulta de alertas.
"""

from datetime import timedelta

from django.utils import timezone

from .consolidation import build_subscription_overview
from .models import Connection, ConnectionStatus

# Gravidade em ordem decrescente. O contador no cabecalho mostra os primeiros da
# lista, entao a ordem importa: aviso informativo antes de conexao quebrada
# esconderia o que precisa de acao.
ALERT_SEVERITY_ORDER = ("danger", "warning", "info")

# A visao de assinaturas ja mostra 30 dias. Alerta com a mesma janela viraria ruido
# permanente, porque sempre existe algo vencendo dentro do mes.
UPCOMING_ALERT_DAYS = 7

# A Pluggy sincroniza sozinha a cada 24h no plano mais lento. Passar disso com
# folga significa dado velho no dashboard sem nada na tela dizendo isso.
STALE_SYNC_DAYS = 3


def _alert(kind: str, severity: str, title: str, detail: str, action_path: str) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "detail": detail,
        "action_path": action_path,
    }


def _subscription_alerts(user, today) -> list[dict]:
    overview = build_subscription_overview(user, today=today, upcoming_days=UPCOMING_ALERT_DAYS)
    alerts = []

    overdue = overview["overdue"]
    if overdue:
        names = ", ".join(item["name"] for item in overdue[:3])
        extra = f" e mais {len(overdue) - 3}" if len(overdue) > 3 else ""
        alerts.append(
            _alert(
                kind="subscription_overdue",
                severity="danger",
                title=f"{len(overdue)} pagamento(s) em atraso",
                detail=f"{names}{extra}. Total: R$ {overview['overdue_total']:.2f}",
                action_path="/subscriptions",
            )
        )

    upcoming = overview["upcoming"]
    if upcoming:
        names = ", ".join(f"{item['name']} ({item['due_date']:%d/%m})" for item in upcoming[:3])
        extra = f" e mais {len(upcoming) - 3}" if len(upcoming) > 3 else ""
        alerts.append(
            _alert(
                kind="subscription_due_soon",
                severity="info",
                title=f"{len(upcoming)} vencimento(s) em {UPCOMING_ALERT_DAYS} dias",
                detail=f"{names}{extra}",
                action_path="/subscriptions",
            )
        )
    return alerts


def _connection_alerts(user, now) -> list[dict]:
    connections = list(
        Connection.objects.filter(user=user).select_related("institution").order_by("id")
    )
    stale_before = now - timedelta(days=STALE_SYNC_DAYS)

    broken = [c for c in connections if c.status == ConnectionStatus.ERROR]
    # Conexao PENDING ainda nao sincronizou por definicao -- nao e dado velho.
    stale = [
        c
        for c in connections
        if c.status == ConnectionStatus.ACTIVE
        and (c.last_synced_at is None or c.last_synced_at < stale_before)
    ]

    alerts = []
    if broken:
        names = ", ".join(c.institution.name for c in broken)
        alerts.append(
            _alert(
                kind="connection_error",
                severity="danger",
                title=f"{len(broken)} conexão(ões) com erro",
                detail=f"{names}. Os dados dessas instituições pararam de atualizar.",
                action_path="/integrations",
            )
        )
    if stale:
        names = ", ".join(c.institution.name for c in stale)
        alerts.append(
            _alert(
                kind="sync_stale",
                severity="warning",
                title=f"{len(stale)} conexão(ões) sem sincronizar",
                detail=f"{names}. Sem atualização há mais de {STALE_SYNC_DAYS} dias.",
                action_path="/integrations",
            )
        )
    return alerts


def build_user_alerts(user) -> list[dict]:
    """Alertas do usuario, do mais grave para o menos.

    Custo fixo: as assinaturas saem de `build_subscription_overview` (3 queries) e
    as conexoes de uma consulta so, com a instituicao no `select_related`.
    """
    now = timezone.now()
    alerts = _subscription_alerts(user, today=timezone.localdate())
    alerts.extend(_connection_alerts(user, now=now))
    alerts.sort(key=lambda alert: ALERT_SEVERITY_ORDER.index(alert["severity"]))
    return alerts
