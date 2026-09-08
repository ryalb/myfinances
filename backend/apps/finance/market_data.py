import json
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from django.utils import timezone

from .investment_categories import TRADABLE_DISPLAY_CATEGORIES, classify_display_category
from .models import Investment, MarketIndexKind, MarketIndexRate, MarketQuote

logger = logging.getLogger(__name__)

# Codigos de serie do SGS (Sistema Gerenciador de Series Temporais do Banco
# Central). https://www3.bcb.gov.br/sgspub -- 11 e 12 sao taxas diarias (%),
# 433 e variacao mensal (%).
SGS_SERIES_BY_INDEX = {
    MarketIndexKind.SELIC: 11,
    MarketIndexKind.CDI: 12,
    MarketIndexKind.IPCA: 433,
}

# Selic/CDI sao diarias e sempre tem ponto recente; IPCA e mensal e o IBGE
# divulga com atraso (por volta do dia 8-10 do mes seguinte) -- uma janela de
# 30 dias pode nao conter nenhum ponto publicado ainda, e o Bacen SGS responde
# 404 "Value(s) not found" nesse caso, nao uma lista vazia. Piso maior evita
# isso sem exigir que quem chama saiba dessa particularidade por indice.
MIN_LOOKBACK_DAYS_BY_INDEX = {
    MarketIndexKind.IPCA: 60,
}


class MarketDataUnavailable(RuntimeError):
    """Bacen SGS fora do ar, sem rede ou resposta em formato inesperado."""


def _parse_sgs_rows(payload: list[dict], *, series_id: int) -> list[dict]:
    """Converte o JSON do Bacen SGS (`[{"data": "dd/mm/aaaa", "valor": "0.05"}]`)
    em linhas prontas para `MarketIndexRate`.

    Compartilhada pelo fetch ao vivo e pela importacao de arquivo: os dois
    consomem exatamente o mesmo formato, a API so muda o transporte.
    """
    rows = []
    for item in payload:
        try:
            reference_date = datetime.strptime(item["data"], "%d/%m/%Y").date()
            value = Decimal(item["valor"])
        except (KeyError, ValueError, InvalidOperation, TypeError):
            # Linha malformada isolada nao deve derrubar a serie inteira.
            logger.warning("Bacen SGS: ponto ignorado na serie %s: %r", series_id, item)
            continue
        rows.append({"reference_date": reference_date, "value": value})
    return rows


def _upsert_rows(kind: MarketIndexKind, rows: list[dict]) -> None:
    for row in rows:
        MarketIndexRate.objects.update_or_create(
            kind=kind,
            reference_date=row["reference_date"],
            defaults={"value": row["value"]},
        )


class BacenSGSClient:
    # A API e publica e sem chave, mas fica atras de um WAF (Azure Front Door +
    # F5 BIG-IP, visiveis nos headers de resposta) que derruba em silencio --
    # sem erro, so timeout -- requisicoes com o User-Agent default do `requests`
    # ("python-requests/x.x.x"), provavel mitigacao generica de scraping.
    # Identificar o cliente com um User-Agent proprio resolve; confirmado com
    # curl (que usa `curl/x.y.z` e funciona) contra o `requests` parado.
    REQUEST_HEADERS = {"User-Agent": "myfinances/1.0"}

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "BACEN_SGS_BASE_URL", "https://api.bcb.gov.br/dados/serie"
        ).rstrip("/")

    def fetch_series(self, kind: MarketIndexKind, since: date) -> list[dict]:
        series_id = SGS_SERIES_BY_INDEX[kind]
        url = f"{self.base_url}/bcdata.sgs.{series_id}/dados"
        params = {"formato": "json", "dataInicial": since.strftime("%d/%m/%Y")}

        try:
            response = requests.get(
                url, params=params, headers=self.REQUEST_HEADERS, timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            # `raise_for_status()` descarta o corpo, e e o corpo que diz o motivo
            # real (Bacen devolve JSON descritivo mesmo em erro -- mesma licao
            # de `_ollama_error_detail` em ai_services.py).
            detail = ""
            response_obj = getattr(exc, "response", None)
            if response_obj is not None:
                detail = f" Resposta: {(response_obj.text or '')[:300]}"
            raise MarketDataUnavailable(
                f"Nao foi possivel falar com o Bacen SGS em {url}: {exc}.{detail}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataUnavailable(
                f"Resposta do Bacen SGS para a serie {series_id} nao e JSON: "
                f"{(response.text or '')[:200]}"
            ) from exc

        return _parse_sgs_rows(payload, series_id=series_id)


def sync_market_index_rates(
    kinds: list[MarketIndexKind] | None = None, lookback_days: int = 30
) -> dict[str, int]:
    """Busca as taxas mais recentes no Bacen SGS e grava em MarketIndexRate.

    Idempotente por (kind, reference_date) via `update_or_create`, mesmo padrao das
    tasks periodicas em `tasks.py`: reexecutar corrige o valor do dia, nunca duplica.
    """
    kinds = kinds or list(MarketIndexKind)
    client = BacenSGSClient()
    today = timezone.localdate()

    synced: dict[str, int] = {}
    for kind in kinds:
        effective_lookback = max(lookback_days, MIN_LOOKBACK_DAYS_BY_INDEX.get(kind, 0))
        since = today - timedelta(days=effective_lookback)
        rows = client.fetch_series(kind, since)
        _upsert_rows(kind, rows)
        synced[kind.value] = len(rows)
        logger.info("Bacen SGS: %s pontos sincronizados para %s", len(rows), kind.value)
    return synced


def import_market_index_rates_from_file(kind: MarketIndexKind, path: str | Path) -> int:
    """Importa uma serie a partir de um JSON local no formato do Bacen SGS.

    Caminho alternativo para quando a rede da maquina bloqueia `api.bcb.gov.br`
    mas o mesmo JSON pode ser baixado por outro meio (navegador, outra rede) --
    o formato esperado e exatamente o que a API devolve com `formato=json`.
    """
    series_id = SGS_SERIES_BY_INDEX[kind]
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)

    rows = _parse_sgs_rows(payload, series_id=series_id)
    _upsert_rows(kind, rows)
    logger.info("Bacen SGS: %s pontos importados de %s para %s", len(rows), path, kind.value)
    return len(rows)


class BrapiClient:
    # Mesma licao do Bacen SGS (ver `BacenSGSClient.REQUEST_HEADERS`): evitar o
    # User-Agent default do `requests`, alvo comum de mitigacao anti-scraping.
    REQUEST_HEADERS = {"User-Agent": "myfinances/1.0"}

    def __init__(self) -> None:
        self.base_url = os.getenv("BRAPI_BASE_URL", "https://brapi.dev/api").rstrip("/")
        # Token obrigatorio em toda chamada -- ver comentario em .env.example.
        self.token = os.getenv("BRAPI_TOKEN", "")

    def check_token_configured(self) -> None:
        if not self.token:
            raise MarketDataUnavailable(
                "BRAPI_TOKEN nao configurado. A API do brapi.dev passou a exigir "
                "token em toda chamada; crie uma conta gratuita em brapi.dev e "
                "defina BRAPI_TOKEN em backend/.env."
            )

    def fetch_quote(self, ticker: str) -> dict | None:
        """Busca a cotacao de um unico ticker.

        Um por chamada, de proposito: o plano gratuito do brapi.dev permite so
        1 ativo por requisicao (`QUOTES_PER_REQUEST_EXCEEDED` ao tentar um lote
        de 11 tickers de uma vez -- o plano Pro permite 20, mas nada garante
        que o usuario tenha ele). Chamar por ticker funciona em qualquer plano.
        """
        self.check_token_configured()
        url = f"{self.base_url}/quote/{ticker}"
        params = {"token": self.token}

        try:
            response = requests.get(
                url, params=params, headers=self.REQUEST_HEADERS, timeout=30
            )
        except requests.RequestException as exc:
            raise MarketDataUnavailable(
                f"Nao foi possivel falar com o brapi.dev em {url}: {exc}"
            ) from exc

        # 404 "NOT_FOUND" e o brapi.dev dizendo que nao tem esse ticker (ex.:
        # direito de subscricao expirado, simbolo fora de cobertura) -- mesmo
        # significado de `results: []` abaixo, so sinalizado como erro HTTP em
        # vez de lista vazia. Nao e falha de infraestrutura, entao nao levanta
        # `MarketDataUnavailable` (visto rodando contra a API real: RECR12).
        if response.status_code == 404:
            return None

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise MarketDataUnavailable(
                f"Nao foi possivel falar com o brapi.dev em {url}: {exc}. "
                f"Resposta: {(response.text or '')[:300]}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataUnavailable(
                f"Resposta do brapi.dev nao e JSON: {(response.text or '')[:200]}"
            ) from exc

        # Ticker invalido/sem cotacao tambem pode sair da lista de `results`
        # com 200 em vez de 404 (`.get` com default cobre isso).
        results = payload.get("results") or []
        return results[0] if results else None



def _parse_optional_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _parse_brapi_quote(item: dict) -> dict | None:
    ticker = item.get("symbol")
    price = item.get("regularMarketPrice")
    if not ticker or price is None:
        return None
    try:
        price_decimal = Decimal(str(price))
    except InvalidOperation:
        return None
    return {
        "ticker": ticker,
        "name": item.get("longName") or item.get("shortName") or "",
        "price": price_decimal,
        "dividend_yield": _parse_optional_decimal(item.get("dividendYield")),
    }


def held_tickers() -> list[str]:
    """Tickers unicos vistos em `Investment.code`, de todos os usuarios --
    apenas os que de fato negociam na B3 (ver `TRADABLE_DISPLAY_CATEGORIES`).

    `MarketQuote` e dado publico compartilhado (mesmo raciocinio de
    `MarketIndexRate`): busca uma vez para o conjunto que qualquer usuario
    possui, nao por usuario. Sem isso, ligar N contas duplicaria a chamada ao
    brapi.dev para o mesmo ticker.
    """
    tickers: set[str] = set()
    for investment in Investment.objects.exclude(code=""):
        if classify_display_category(investment).key in TRADABLE_DISPLAY_CATEGORIES:
            tickers.add(investment.code)
    return list(tickers)


def sync_market_quotes_for_held_tickers() -> int:
    """Busca no brapi.dev a cotacao dos tickers que aparecem em algum
    `Investment.code` e grava em MarketQuote.

    So os tickers que o usuario efetivamente possui -- nunca a lista completa
    do mercado, que e o dado proprietario que reports como o da Suno vendem.
    """
    tickers = held_tickers()
    if not tickers:
        return 0

    client = BrapiClient()
    client.check_token_configured()
    today = timezone.localdate()

    count = 0
    for ticker in tickers:
        try:
            item = client.fetch_quote(ticker)
        except MarketDataUnavailable:
            # Falha de rede/formato e por ticker agora (uma chamada cada, ver
            # `BrapiClient.fetch_quote`); um ticker instavel nao pode abortar
            # os demais -- mesmo raciocinio de `snapshot_all_users` em tasks.py.
            logger.exception("brapi.dev: falha ao buscar cotacao de %s", ticker)
            continue

        if item is None:
            logger.info("brapi.dev: sem cotacao disponivel para %s", ticker)
            continue
        parsed = _parse_brapi_quote(item)
        if parsed is None:
            logger.warning("brapi.dev: cotacao ignorada, campo obrigatorio ausente: %r", item)
            continue
        MarketQuote.objects.update_or_create(
            ticker=parsed["ticker"],
            as_of_date=today,
            defaults={
                "price": parsed["price"],
                "dividend_yield": parsed["dividend_yield"],
                "name": parsed["name"],
                "source": "brapi",
            },
        )
        count += 1

    logger.info("brapi.dev: %s cotacoes sincronizadas de %s tickers pedidos", count, len(tickers))
    return count


