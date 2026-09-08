"""Testes da sincronizacao de indices de referencia (Selic, CDI, IPCA) via Bacen SGS.

Sem chamada de rede real: `requests.get` e substituido por um fake em memoria,
mesmo padrao de `FakePluggyClient` em conftest.py.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import requests
from django.utils import timezone

from apps.finance.market_data import (
    MarketDataUnavailable,
    import_market_index_rates_from_file,
    sync_market_index_rates,
)
from apps.finance.models import MarketIndexKind, MarketIndexRate


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        if self._payload is None:
            raise ValueError("no payload")
        return self._payload


SGS_PAYLOAD_BY_SERIES = {
    11: [{"data": "01/07/2026", "valor": "0.036523"}, {"data": "02/07/2026", "valor": "0.036789"}],
    12: [{"data": "01/07/2026", "valor": "0.035000"}],
    433: [{"data": "01/06/2026", "valor": "0.50"}],
}


@pytest.fixture
def fake_sgs(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        series_id = int(url.rsplit(".", 1)[-1].split("/")[0])
        return FakeResponse(payload=SGS_PAYLOAD_BY_SERIES.get(series_id, []))

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


@pytest.mark.django_db
def test_fetch_sends_a_non_default_user_agent(fake_sgs):
    """Bacen SGS derruba em silencio o User-Agent default do `requests` -- ver
    comentario em `BacenSGSClient.REQUEST_HEADERS`. Sem este teste, remover o
    header por engano reintroduz o hang sem nenhum teste denunciando."""
    sync_market_index_rates(kinds=[MarketIndexKind.SELIC])

    assert len(fake_sgs) == 1
    user_agent = fake_sgs[0]["headers"]["User-Agent"]
    assert "python-requests" not in user_agent


@pytest.mark.django_db
def test_ipca_uses_a_wider_lookback_window_than_the_default(fake_sgs):
    """IPCA e mensal e o IBGE divulga com atraso (~dia 8-10 do mes seguinte) --
    a janela de 30 dias que basta para Selic/CDI (diarias) pode nao conter
    nenhum ponto publicado ainda, e o Bacen SGS responde 404 "Value(s) not
    found" nesse caso, nao lista vazia. Ver `MIN_LOOKBACK_DAYS_BY_INDEX`."""
    sync_market_index_rates(kinds=[MarketIndexKind.IPCA], lookback_days=30)

    assert len(fake_sgs) == 1
    sent_data_inicial = fake_sgs[0]["params"]["dataInicial"]
    since = datetime.strptime(sent_data_inicial, "%d/%m/%Y").date()
    assert since <= timezone.localdate() - timedelta(days=60)


@pytest.mark.django_db
def test_sync_creates_one_row_per_point(fake_sgs):
    synced = sync_market_index_rates(kinds=[MarketIndexKind.SELIC])

    assert synced == {"selic": 2}
    rates = list(
        MarketIndexRate.objects.filter(kind=MarketIndexKind.SELIC).order_by("reference_date")
    )
    assert [r.reference_date for r in rates] == [date(2026, 7, 1), date(2026, 7, 2)]
    assert rates[0].value == Decimal("0.036523")


@pytest.mark.django_db
def test_sync_is_idempotent_by_kind_and_date(fake_sgs):
    sync_market_index_rates(kinds=[MarketIndexKind.CDI])
    sync_market_index_rates(kinds=[MarketIndexKind.CDI])

    assert MarketIndexRate.objects.filter(kind=MarketIndexKind.CDI).count() == 1


@pytest.mark.django_db
def test_sync_overwrites_the_value_for_an_existing_date(monkeypatch):
    MarketIndexRate.objects.create(
        kind=MarketIndexKind.IPCA, reference_date=date(2026, 6, 1), value=Decimal("0.10")
    )

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(payload=[{"data": "01/06/2026", "valor": "0.50"}])

    monkeypatch.setattr(requests, "get", fake_get)
    sync_market_index_rates(kinds=[MarketIndexKind.IPCA])

    rate = MarketIndexRate.objects.get(kind=MarketIndexKind.IPCA, reference_date=date(2026, 6, 1))
    assert rate.value == Decimal("0.50")


@pytest.mark.django_db
def test_malformed_points_are_skipped_without_failing_the_batch(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            payload=[
                {"data": "01/07/2026", "valor": "0.036523"},
                {"data": "not-a-date", "valor": "0.05"},
                {"data": "02/07/2026"},
            ]
        )

    monkeypatch.setattr(requests, "get", fake_get)
    synced = sync_market_index_rates(kinds=[MarketIndexKind.SELIC])

    assert synced == {"selic": 1}


@pytest.mark.django_db
def test_connection_error_raises_actionable_exception(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(MarketDataUnavailable):
        sync_market_index_rates(kinds=[MarketIndexKind.SELIC])


@pytest.mark.django_db
def test_non_json_response_raises_actionable_exception(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(payload=None, text="<html>gateway timeout</html>")

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(MarketDataUnavailable):
        sync_market_index_rates(kinds=[MarketIndexKind.SELIC])


# --------------------------------------------------------------------------
# Importacao de arquivo (sem rede) -- caminho alternativo para redes que
# bloqueiam api.bcb.gov.br.
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_import_from_file_creates_one_row_per_point(tmp_path):
    path = tmp_path / "selic.json"
    path.write_text(
        '[{"data": "01/07/2026", "valor": "0.036523"}, '
        '{"data": "02/07/2026", "valor": "0.036789"}]',
        encoding="utf-8",
    )

    count = import_market_index_rates_from_file(MarketIndexKind.SELIC, path)

    assert count == 2
    rates = list(
        MarketIndexRate.objects.filter(kind=MarketIndexKind.SELIC).order_by("reference_date")
    )
    assert [r.reference_date for r in rates] == [date(2026, 7, 1), date(2026, 7, 2)]
    assert rates[1].value == Decimal("0.036789")


@pytest.mark.django_db
def test_import_from_file_is_idempotent_and_overwrites_existing_dates(tmp_path):
    MarketIndexRate.objects.create(
        kind=MarketIndexKind.IPCA, reference_date=date(2026, 6, 1), value=Decimal("0.10")
    )
    path = tmp_path / "ipca.json"
    path.write_text('[{"data": "01/06/2026", "valor": "0.50"}]', encoding="utf-8")

    import_market_index_rates_from_file(MarketIndexKind.IPCA, path)

    assert MarketIndexRate.objects.filter(kind=MarketIndexKind.IPCA).count() == 1
    rate = MarketIndexRate.objects.get(kind=MarketIndexKind.IPCA, reference_date=date(2026, 6, 1))
    assert rate.value == Decimal("0.50")


@pytest.mark.django_db
def test_import_from_file_skips_malformed_points(tmp_path):
    path = tmp_path / "selic.json"
    path.write_text(
        '[{"data": "01/07/2026", "valor": "0.036523"}, '
        '{"data": "not-a-date", "valor": "0.05"}, '
        '{"data": "02/07/2026"}]',
        encoding="utf-8",
    )

    count = import_market_index_rates_from_file(MarketIndexKind.SELIC, path)

    assert count == 1

