"""Testes da sincronizacao de cotacoes de mercado (brapi.dev), escopada aos
tickers que aparecem em `Investment.code`.

Sem chamada de rede real: `requests.get` e substituido por um fake em memoria,
mesmo padrao de test_market_data.py.
"""

from decimal import Decimal

import pytest
import requests
from django.utils import timezone

from apps.finance.market_data import (
    MarketDataUnavailable,
    held_tickers,
    sync_market_quotes_for_held_tickers,
)
from apps.finance.models import Investment, MarketQuote


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


FAKE_QUOTES_BY_TICKER = {
    "PMLL11": {
        "symbol": "PMLL11",
        "longName": "Fundo Malls",
        "regularMarketPrice": 102.65,
        "dividendYield": 11.7,
    },
    "BTLG11": {
        "symbol": "BTLG11",
        "longName": "Fundo Logistico",
        "regularMarketPrice": 99.45,
        "dividendYield": 9.8,
    },
}


@pytest.fixture
def fake_brapi(monkeypatch):
    monkeypatch.setenv("BRAPI_TOKEN", "test-token")
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        ticker = url.rsplit("/", 1)[-1]
        results = [FAKE_QUOTES_BY_TICKER[ticker]] if ticker in FAKE_QUOTES_BY_TICKER else []
        return FakeResponse(payload={"results": results})

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


def _make_investment(connection, code, external_id="inv-1", kind="EQUITY"):
    return Investment.objects.create(
        connection=connection, external_id=external_id, name=code, kind=kind, code=code
    )


@pytest.mark.django_db
def test_held_tickers_returns_unique_non_blank_codes(connection):
    _make_investment(connection, "PMLL11", external_id="i1")
    _make_investment(connection, "PMLL11", external_id="i2")
    _make_investment(connection, "", external_id="i3")

    assert held_tickers() == ["PMLL11"]


@pytest.mark.django_db
def test_sync_is_a_noop_without_held_tickers(fake_brapi):
    count = sync_market_quotes_for_held_tickers()

    assert count == 0
    assert fake_brapi == []


@pytest.mark.django_db
def test_sync_creates_one_quote_per_held_ticker(connection, fake_brapi):
    _make_investment(connection, "PMLL11")

    count = sync_market_quotes_for_held_tickers()

    assert count == 1
    quote = MarketQuote.objects.get(ticker="PMLL11")
    assert quote.price == Decimal("102.65")
    assert quote.dividend_yield == Decimal("11.7")
    assert quote.name == "Fundo Malls"
    assert quote.source == "brapi"
    assert quote.as_of_date == timezone.localdate()


@pytest.mark.django_db
def test_sync_only_requests_tickers_actually_held(connection, fake_brapi):
    """Um ticker por chamada agora (ver `BrapiClient.fetch_quote`): dois
    tickers possuidos geram duas chamadas, uma cada -- nunca um lote."""
    _make_investment(connection, "PMLL11", external_id="i1")
    _make_investment(connection, "BTLG11", external_id="i2")

    sync_market_quotes_for_held_tickers()

    requested = {call["url"].rsplit("/", 1)[-1] for call in fake_brapi}
    assert requested == {"PMLL11", "BTLG11"}


@pytest.mark.django_db
def test_sync_skips_tickers_missing_from_the_response(connection, fake_brapi):
    _make_investment(connection, "ZZZZ99")

    count = sync_market_quotes_for_held_tickers()

    assert count == 0
    assert not MarketQuote.objects.exists()


@pytest.mark.django_db
def test_sync_is_idempotent_for_the_same_day(connection, fake_brapi):
    _make_investment(connection, "PMLL11")

    sync_market_quotes_for_held_tickers()
    sync_market_quotes_for_held_tickers()

    assert MarketQuote.objects.filter(ticker="PMLL11").count() == 1


@pytest.mark.django_db
def test_sync_sends_a_non_default_user_agent(connection, fake_brapi):
    """Mesma mitigacao anti-scraping observada no Bacen SGS (ver
    `BacenSGSClient.REQUEST_HEADERS`) pode existir aqui tambem -- identificar o
    cliente evita reintroduzir o mesmo hang em silencio."""
    _make_investment(connection, "PMLL11")

    sync_market_quotes_for_held_tickers()

    assert len(fake_brapi) == 1
    assert "python-requests" not in fake_brapi[0]["headers"]["User-Agent"]


@pytest.mark.django_db
def test_held_tickers_excludes_fixed_income_and_unlisted_funds(connection):
    """`Investment.code` para renda fixa pode ser um CNPJ de emissor ou codigo
    de debenture/CRA, nunca um ticker -- mandar isso pro brapi.dev so gera
    pedido que nunca vai casar (foi o que aconteceu na primeira tentativa real:
    CRA024002ML, CRA024009Q3 e um CNPJ foram pro pedido junto dos tickers)."""
    _make_investment(connection, "CRA024002ML", external_id="i1", kind="FIXED_INCOME")
    _make_investment(connection, "45.088.790/0001-47", external_id="i2", kind="FIXED_INCOME")
    _make_investment(connection, "PMLL11", external_id="i3", kind="EQUITY")

    assert held_tickers() == ["PMLL11"]


@pytest.mark.django_db
def test_missing_token_raises_actionable_exception(connection, monkeypatch):
    monkeypatch.delenv("BRAPI_TOKEN", raising=False)
    _make_investment(connection, "PMLL11")

    with pytest.raises(MarketDataUnavailable):
        sync_market_quotes_for_held_tickers()


@pytest.mark.django_db
def test_connection_error_for_one_ticker_does_not_abort_the_others(connection, monkeypatch):
    """Cada ticker e uma chamada isolada agora -- uma falhando nao pode
    derrubar as demais, mesmo raciocinio de `snapshot_all_users` em tasks.py."""
    monkeypatch.setenv("BRAPI_TOKEN", "test-token")
    _make_investment(connection, "PMLL11", external_id="i1")
    _make_investment(connection, "BTLG11", external_id="i2")

    def fake_get(url, params=None, headers=None, timeout=None):
        ticker = url.rsplit("/", 1)[-1]
        if ticker == "PMLL11":
            raise requests.ConnectionError("boom")
        return FakeResponse(payload={"results": [FAKE_QUOTES_BY_TICKER[ticker]]})

    monkeypatch.setattr(requests, "get", fake_get)

    count = sync_market_quotes_for_held_tickers()

    assert count == 1
    assert MarketQuote.objects.filter(ticker="BTLG11").exists()
    assert not MarketQuote.objects.filter(ticker="PMLL11").exists()


@pytest.mark.django_db
def test_non_json_response_for_a_ticker_is_skipped_without_raising(connection, monkeypatch):
    monkeypatch.setenv("BRAPI_TOKEN", "test-token")
    _make_investment(connection, "PMLL11")

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(payload=None, text="<html>gateway timeout</html>")

    monkeypatch.setattr(requests, "get", fake_get)

    count = sync_market_quotes_for_held_tickers()

    assert count == 0
    assert not MarketQuote.objects.exists()


@pytest.mark.django_db
def test_404_not_found_for_a_ticker_is_treated_as_no_quote(connection, monkeypatch):
    """Visto rodando contra a API real: RECR12 devolveu 404 `NOT_FOUND`
    (provavel direito de subscricao expirado, fora de cobertura do brapi.dev).
    Isso e ausencia de dado para aquele ticker, nao falha de infraestrutura --
    nao deve gerar traceback nem contar como erro."""
    monkeypatch.setenv("BRAPI_TOKEN", "test-token")
    _make_investment(connection, "PMLL11", external_id="i1")
    _make_investment(connection, "RECR12", external_id="i2")

    def fake_get(url, params=None, headers=None, timeout=None):
        ticker = url.rsplit("/", 1)[-1]
        if ticker == "RECR12":
            return FakeResponse(
                payload={"error": True, "message": "Nao encontrado", "code": "NOT_FOUND"},
                status_code=404,
            )
        return FakeResponse(payload={"results": [FAKE_QUOTES_BY_TICKER[ticker]]})

    monkeypatch.setattr(requests, "get", fake_get)

    count = sync_market_quotes_for_held_tickers()

    assert count == 1
    assert MarketQuote.objects.filter(ticker="PMLL11").exists()
    assert not MarketQuote.objects.filter(ticker="RECR12").exists()


@pytest.mark.django_db
def test_error_shaped_response_is_treated_as_zero_quotes(connection, monkeypatch):
    """Quando nenhum ticker pedido e reconhecido, o brapi.dev responde um
    formato de erro global (`{"error": true, ...}`) em vez de `results: []`."""
    monkeypatch.setenv("BRAPI_TOKEN", "test-token")
    _make_investment(connection, "ZZZZ99")

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(payload={"error": True, "message": "ticker nao encontrado"})

    monkeypatch.setattr(requests, "get", fake_get)

    count = sync_market_quotes_for_held_tickers()

    assert count == 0

