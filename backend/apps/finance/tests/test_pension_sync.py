"""Testes da sincronizacao de previdencia privada.

O filtro original era `type in ("pension", "previdencia")`, e isso nunca casava com
nada: na Pluggy previdencia privada e `type: "SECURITY"` com `subtype` em
`RETIREMENT | PGBL | VGBL`. Nao existe `type: "PENSION"` no enum -- os tipos sao
FIXED_INCOME, SECURITY, MUTUAL_FUND, EQUITY, ETF e COE.
Ver https://docs.pluggy.ai/docs/investments.

Consequencia: a previdencia sumia da tela, mas continuava entrando como `Investment`
generico, porque o laco de investimentos nao filtra nada.
"""

from decimal import Decimal

import pytest

from apps.finance.consolidation import build_user_financial_summary
from apps.finance.models import Investment, PensionPlan, SyncJob
from apps.finance.tasks import _sync_pension_plans, sync_connection_data
from apps.finance.tests.conftest import FakePluggyClient

PREVIDENCIA = {
    "id": "inv-prev-1",
    "name": "Rico PREVIDENCIA",
    "type": "SECURITY",
    "subtype": "RETIREMENT",
    "balance": 1359.39,
    "amount": 1500,
    "value": 500,
    "quantity": 3,
    "currencyCode": "BRL",
    "institution": {
        "name": "BANCO BTG PACTUAL S/A",
        "insurer": {"name": "BRADESCO VIDA E PREVIDÊNCIA S.A."},
    },
}

CDB = {
    "id": "inv-cdb-1",
    "name": "CDB BANCO MAXIMA",
    "type": "FIXED_INCOME",
    "subtype": "CDB",
    "balance": 2000,
    "value": 2000,
    "quantity": 1,
    "currencyCode": "BRL",
}


@pytest.mark.django_db
def test_security_investment_becomes_a_pension_plan(connection):
    client = FakePluggyClient(investments=[PREVIDENCIA])

    _sync_pension_plans(client, connection)

    plan = PensionPlan.objects.get(connection=connection)
    assert plan.external_id == "inv-prev-1"
    assert plan.name == "Rico PREVIDENCIA"
    assert plan.balance == Decimal("1359.39")


@pytest.mark.django_db
@pytest.mark.parametrize("subtype", ["RETIREMENT", "PGBL", "VGBL"])
def test_every_documented_pension_subtype_is_recognized(connection, subtype):
    client = FakePluggyClient(investments=[{**PREVIDENCIA, "subtype": subtype}])

    _sync_pension_plans(client, connection)

    assert PensionPlan.objects.filter(connection=connection).exists()


@pytest.mark.django_db
def test_pension_is_recognized_even_without_subtype(connection):
    """`subtype` e opcional na Pluggy; `type` e obrigatorio. Depender do subtype
    deixaria a previdencia de fora quando o provedor nao o preenche."""
    payload = {k: v for k, v in PREVIDENCIA.items() if k != "subtype"}
    client = FakePluggyClient(investments=[payload])

    _sync_pension_plans(client, connection)

    assert PensionPlan.objects.filter(connection=connection).exists()


@pytest.mark.django_db
def test_non_pension_investment_does_not_become_a_pension_plan(connection):
    client = FakePluggyClient(investments=[CDB])

    _sync_pension_plans(client, connection)

    assert not PensionPlan.objects.exists()


@pytest.mark.django_db
def test_provider_comes_from_the_insurer_when_present(connection):
    """A seguradora e quem de fato administra a previdencia, e nem sempre e a
    corretora pela qual ela foi contratada."""
    client = FakePluggyClient(investments=[PREVIDENCIA])

    _sync_pension_plans(client, connection)

    assert PensionPlan.objects.get(connection=connection).provider == (
        "BRADESCO VIDA E PREVIDÊNCIA S.A."
    )


@pytest.mark.django_db
def test_provider_falls_back_to_the_connection_institution(connection):
    """`provider` nao existe no payload da Pluggy -- o codigo antigo lia esse campo
    e gravava string vazia sempre."""
    payload = {k: v for k, v in PREVIDENCIA.items() if k != "institution"}
    client = FakePluggyClient(investments=[payload])

    _sync_pension_plans(client, connection)

    plan = PensionPlan.objects.get(connection=connection)
    assert plan.provider == connection.institution.name
    assert plan.provider != ""


@pytest.mark.django_db
def test_resyncing_updates_instead_of_duplicating(connection):
    client = FakePluggyClient(investments=[PREVIDENCIA])
    _sync_pension_plans(client, connection)

    _sync_pension_plans(
        FakePluggyClient(investments=[{**PREVIDENCIA, "balance": 2000}]), connection
    )

    plans = PensionPlan.objects.filter(connection=connection)
    assert plans.count() == 1
    assert plans.first().balance == Decimal("2000")


# --------------------------------------------------------------------------
# Contagem dupla no patrimonio
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_pension_is_not_also_stored_as_a_generic_investment(connection, monkeypatch):
    """O laco de investimentos criava um `Investment` para tudo que a Pluggy devolve,
    inclusive a previdencia. Com o filtro de previdencia corrigido, o mesmo ativo
    entraria como `InvestmentPosition.market_value` **e** como `PensionPlan.balance`
    -- somando duas vezes no patrimonio."""
    from apps.finance import tasks

    monkeypatch.setattr(
        tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[PREVIDENCIA, CDB])
    )
    sync_job = SyncJob.objects.create(connection=connection, kind="full")

    sync_connection_data(sync_job.id)

    assert PensionPlan.objects.filter(external_id="inv-prev-1").exists()
    assert not Investment.objects.filter(
        external_id="inv-prev-1"
    ).exists(), "previdencia gravada tambem como investimento generico"
    assert Investment.objects.filter(external_id="inv-cdb-1").exists(), "CDB deveria entrar"


@pytest.mark.django_db
def test_net_worth_counts_the_pension_once(user, connection, monkeypatch):
    from apps.finance import tasks

    monkeypatch.setattr(
        tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[PREVIDENCIA])
    )
    sync_job = SyncJob.objects.create(connection=connection, kind="full")

    sync_connection_data(sync_job.id)

    summary = build_user_financial_summary(user)
    assert summary["assets"] == Decimal("1359.39")
    assert summary["breakdown"]["pension"] == Decimal("1359.39")
    assert summary["breakdown"]["investments"] == Decimal("0")


@pytest.mark.django_db
def test_unit_price_uses_the_quota_value_field(connection, monkeypatch):
    """A Pluggy expoe o valor da cota em `value`; o codigo lia `price`, que nao
    existe no payload -- entao `unit_price` era sempre zero."""
    from apps.finance import tasks

    monkeypatch.setattr(tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[CDB]))
    sync_job = SyncJob.objects.create(connection=connection, kind="full")

    sync_connection_data(sync_job.id)

    position = Investment.objects.get(external_id="inv-cdb-1").positions.first()
    assert position.unit_price == Decimal("2000")


# --------------------------------------------------------------------------
# Posicoes liquidadas
# --------------------------------------------------------------------------

WITHDRAWN = {
    "id": "inv-out-1",
    "name": "XPML12",
    "type": "EQUITY",
    "subtype": "STOCK",
    "status": "TOTAL_WITHDRAWAL",
    "balance": 0,
    "value": 0,
    "quantity": 0,
    "currencyCode": "BRL",
}


@pytest.mark.django_db
def test_withdrawn_position_is_not_stored(connection, monkeypatch):
    """O sync gravava toda posicao devolvida, inclusive as ja vendidas, e a lista de
    investimentos acumulava linhas zeradas."""
    from apps.finance import tasks

    monkeypatch.setattr(
        tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[WITHDRAWN, CDB])
    )
    sync_job = SyncJob.objects.create(connection=connection, kind="full")

    sync_connection_data(sync_job.id)

    assert not Investment.objects.filter(external_id="inv-out-1").exists()
    assert Investment.objects.filter(external_id="inv-cdb-1").exists(), "CDB ativo deveria entrar"


@pytest.mark.django_db
def test_a_position_that_becomes_withdrawn_is_removed(connection, monkeypatch):
    """Pular sem remover deixaria a linha antiga para sempre. O historico agregado
    de patrimonio vive em NetWorthSnapshot, nao aqui."""
    from apps.finance import tasks

    active = {**WITHDRAWN, "status": "ACTIVE", "balance": 3031.95}
    monkeypatch.setattr(
        tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[active])
    )
    sync_connection_data(SyncJob.objects.create(connection=connection, kind="full").id)
    assert Investment.objects.filter(external_id="inv-out-1").exists()

    monkeypatch.setattr(
        tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[WITHDRAWN])
    )
    sync_connection_data(SyncJob.objects.create(connection=connection, kind="full").id)

    assert not Investment.objects.filter(external_id="inv-out-1").exists()


@pytest.mark.django_db
def test_active_and_pending_positions_are_kept(connection, monkeypatch):
    """Só `TOTAL_WITHDRAWAL` sai. `PENDING` é compra em validação, não liquidação."""
    from apps.finance import tasks

    pending = {**CDB, "id": "inv-pending", "status": "PENDING"}
    monkeypatch.setattr(
        tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[pending])
    )

    sync_connection_data(SyncJob.objects.create(connection=connection, kind="full").id)

    assert Investment.objects.filter(external_id="inv-pending").exists()


@pytest.mark.django_db
def test_investment_without_status_is_kept(connection, monkeypatch):
    """`status` é opcional na Pluggy; ausência não significa liquidado."""
    from apps.finance import tasks

    monkeypatch.setattr(tasks, "PluggyClient", lambda *a, **k: FakePluggyClient(investments=[CDB]))

    sync_connection_data(SyncJob.objects.create(connection=connection, kind="full").id)

    assert Investment.objects.filter(external_id="inv-cdb-1").exists()
