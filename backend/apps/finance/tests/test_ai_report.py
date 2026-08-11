"""Testes do relatorio de IA: forma da resposta e moderacao.

A LLM devolve JSON livre. Sem normalizacao a UI quebra na primeira variacao
(`strengths` como string em vez de lista, `summary` ausente), e o usuario ve uma
tela vazia sem saber por que.

A moderacao aqui e sobre para onde o dado sensivel vai: o plano afirma "100%
offline/local sem envio de dados para APIs externas", e nada garantia isso -- um
`OLLAMA_URL` apontando para fora mandaria saldo, transacoes e instituicoes para um
terceiro em silencio.
"""

import pytest

from apps.finance.ai_services import (
    REPORT_DISCLAIMER,
    AIServiceUnavailable,
    LLMService,
    RAGService,
    assert_local_inference,
    normalize_report,
)

# --------------------------------------------------------------------------
# Forma da resposta
# --------------------------------------------------------------------------


def test_missing_keys_become_empty_values():
    report = normalize_report({})

    assert report["summary"] == ""
    assert report["projections"] == ""
    assert report["strengths"] == []
    assert report["weaknesses"] == []
    assert report["adjustments"] == []
    assert report["suggestions"] == []


def test_string_in_a_list_field_becomes_a_single_item_list():
    """Peca comum do modelo: devolver um paragrafo onde o contrato pede lista."""
    report = normalize_report({"strengths": "Boa reserva de emergencia"})

    assert report["strengths"] == ["Boa reserva de emergencia"]


def test_multiline_string_in_a_list_field_becomes_one_item_per_line():
    report = normalize_report({"weaknesses": "Gasto alto\nSem reserva\n\n"})

    assert report["weaknesses"] == ["Gasto alto", "Sem reserva"]


def test_list_in_a_text_field_is_joined():
    report = normalize_report({"summary": ["Primeira parte.", "Segunda parte."]})

    assert report["summary"] == "Primeira parte. Segunda parte."


def test_non_string_items_are_coerced_and_empties_dropped():
    report = normalize_report({"suggestions": ["Tesouro Selic", "", None, 42]})

    assert report["suggestions"] == ["Tesouro Selic", "42"]


def test_nested_objects_in_a_list_are_flattened_to_text():
    """Modelo as vezes devolve `[{"titulo": ..., "detalhe": ...}]`. Renderizar isso
    como `[object Object]` seria pior que serializar."""
    report = normalize_report({"adjustments": [{"acao": "Reduzir cartao"}]})

    assert len(report["adjustments"]) == 1
    assert "Reduzir cartao" in report["adjustments"][0]


def test_dict_item_in_a_list_drops_redundant_raw_numbers():
    """Bug real: modelo devolveu `{"ponto": "...", "valor": 180149.3, "moeda": "BRL"}`
    e o item flattened virava "frase — 180149.3 — BRL", repetindo em numero cru o
    que a frase ja dizia."""
    report = normalize_report(
        {
            "strengths": [
                {"ponto": "Reserva de emergencia solida", "valor": 180149.3, "moeda": "BRL"}
            ]
        }
    )

    assert report["strengths"] == ["Reserva de emergencia solida"]


def test_dict_in_a_text_field_drops_redundant_raw_numbers():
    """Mesmo bug, mas no campo de texto: a "Resumo" da UI mostrava so os numeros
    crus concatenados porque o modelo devolveu um dict em vez de string."""
    report = normalize_report(
        {"summary": {"texto": "Patrimonio saudavel e diversificado", "valor": 328137.21}}
    )

    assert report["summary"] == "Patrimonio saudavel e diversificado"


def test_dict_with_only_numbers_falls_back_to_joining_them():
    """Sem nenhum texto descritivo sobrando, ainda assim tem que devolver algo em
    vez de string vazia."""
    report = normalize_report({"summary": {"ativos": 100, "passivos": 50}})

    assert report["summary"] == "100 — 50"


def test_none_report_does_not_explode():
    report = normalize_report(None)

    assert report["summary"] == ""
    assert report["strengths"] == []


def test_unknown_keys_are_dropped():
    """O contrato com a UI e fechado: chave que ela nao renderiza nao deve viajar."""
    report = normalize_report({"summary": "ok", "inventado": "valor"})

    assert "inventado" not in report


def test_disclaimer_is_always_attached():
    report = normalize_report({"summary": "ok"})

    assert report["disclaimer"] == REPORT_DISCLAIMER
    assert "recomendação de investimento" in REPORT_DISCLAIMER


def test_disclaimer_cannot_be_overwritten_by_the_model():
    report = normalize_report({"disclaimer": "invista tudo em cripto"})

    assert report["disclaimer"] == REPORT_DISCLAIMER


# --------------------------------------------------------------------------
# Moderacao: para onde o dado sensivel vai
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://[::1]:11434",
        "http://ollama:11434",
    ],
)
def test_local_inference_urls_are_accepted(url, monkeypatch):
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)

    assert_local_inference(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com",
        "http://192.168.1.50:11434",
        "https://ollama.exemplo.com",
    ],
)
def test_remote_inference_is_refused_by_default(url, monkeypatch):
    """O contexto enviado ao modelo contem saldo, transacoes e instituicoes."""
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)

    with pytest.raises(AIServiceUnavailable, match="AI_ALLOW_REMOTE_INFERENCE"):
        assert_local_inference(url)


def test_remote_inference_can_be_opted_into(monkeypatch):
    monkeypatch.setenv("AI_ALLOW_REMOTE_INFERENCE", "true")

    assert_local_inference("https://ollama.exemplo.com")


def test_llm_service_refuses_to_start_against_a_remote_host(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "https://ollama.exemplo.com")

    with pytest.raises(AIServiceUnavailable, match="AI_ALLOW_REMOTE_INFERENCE"):
        LLMService()


# --------------------------------------------------------------------------
# Erros do Ollama precisam ser acionaveis
# --------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _stub_post(monkeypatch, response):
    monkeypatch.setattr("apps.finance.ai_services.requests.post", lambda *a, **k: response)


def test_missing_model_error_repeats_what_ollama_said_and_how_to_fix(monkeypatch):
    """O caso real: o Ollama responde 404 com `model "X" not found, try pulling it
    first`, e `raise_for_status()` descartava isso, sobrando "404 Client Error" --
    indistinguivel de endpoint inexistente."""
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    _stub_post(
        monkeypatch,
        FakeResponse(404, {"error": 'model "nomic-embed-text" not found, try pulling it first'}),
    )

    with pytest.raises(AIServiceUnavailable) as excinfo:
        RAGService()._get_embedding("qualquer texto")

    message = str(excinfo.value)
    assert "not found" in message, "perdeu a mensagem do Ollama"
    assert "ollama pull nomic-embed-text" in message, "nao diz como resolver"


def test_server_without_embedding_support_surfaces_the_reason(monkeypatch):
    """Modelo de completion no endpoint de embeddings devolve 500 com uma mensagem
    propria -- que tambem precisa chegar ao usuario."""
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    _stub_post(
        monkeypatch,
        FakeResponse(500, {"error": "This server does not support embeddings."}),
    )

    with pytest.raises(AIServiceUnavailable, match="does not support embeddings"):
        RAGService()._get_embedding("qualquer texto")


def test_non_json_error_body_still_produces_a_message(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    _stub_post(monkeypatch, FakeResponse(502, None, text="<html>Bad Gateway</html>"))

    with pytest.raises(AIServiceUnavailable, match="502"):
        RAGService()._get_embedding("qualquer texto")


def test_missing_chat_model_error_is_actionable(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "qwen2.5:14b")
    _stub_post(
        monkeypatch,
        FakeResponse(404, {"error": 'model "qwen2.5:14b" not found, try pulling it first'}),
    )

    with pytest.raises(AIServiceUnavailable) as excinfo:
        LLMService().generate_portfolio_report(context_chunks=[])

    assert "ollama pull qwen2.5:14b" in str(excinfo.value)


class FakeChunk:
    def __init__(self, source_type, source_id, content):
        self.source_type = source_type
        self.source_id = source_id
        self.content = content


def _stub_ollama(monkeypatch, payload: str):
    _stub_post(monkeypatch, FakeResponse(200, {"response": payload}))


def test_report_is_normalized_and_carries_retrieved_sources(monkeypatch):
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    _stub_ollama(monkeypatch, '{"summary": "Tudo certo", "strengths": "Reserva boa"}')

    context = [
        {"chunk": FakeChunk("financial_summary", "1", "Ativos: 100"), "similarity": 1.0},
        {"chunk": FakeChunk("transactions", "2026-08", "Mercado 50"), "similarity": 0.8123456},
    ]

    report = LLMService().generate_portfolio_report(context_chunks=context)

    assert report["summary"] == "Tudo certo"
    assert report["strengths"] == ["Reserva boa"]
    assert report["disclaimer"] == REPORT_DISCLAIMER
    assert report["sources"] == [
        {"source_type": "financial_summary", "source_id": "1", "similarity": 1.0},
        {"source_type": "transactions", "source_id": "2026-08", "similarity": 0.8123},
    ]


def test_invalid_json_keeps_the_raw_text_as_summary(monkeypatch):
    """`format=json` do Ollama nao garante JSON valido. Perder a resposta inteira
    seria pior que mostrar o texto cru."""
    monkeypatch.delenv("AI_ALLOW_REMOTE_INFERENCE", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    _stub_ollama(monkeypatch, "isto nao e json")

    report = LLMService().generate_portfolio_report(context_chunks=[])

    assert report["summary"] == "isto nao e json"
    assert report["strengths"] == []
    assert report["disclaimer"] == REPORT_DISCLAIMER
