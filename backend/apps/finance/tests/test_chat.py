"""Testes do chat de IA sobre dados financeiros.

Ao contrario dos quatro relatorios de IA (`test_executive_report.py` e afins,
um por usuario, "Reanalisar" substitui), aqui cada POST acrescenta um turno a
uma conversa continua -- GET devolve o historico inteiro, DELETE limpa. A
resposta e um `StreamingHttpResponse`: os testes consomem `response.streaming_
content` explicitamente, que e como o Django dispara o codigo da view (o
`generate()` da view, incluindo o `finally` que persiste a mensagem do
assistente, so roda quando o gerador e iterado).
"""

import pytest
from rest_framework.test import APIClient

from apps.finance.ai_services import AIServiceUnavailable
from apps.finance.models import ChatMessage, ChatMessageRole

CHAT_URL = "/api/v1/ai/chat/"


class FakeChunk:
    def __init__(self, source_type, source_id):
        self.source_type = source_type
        self.source_id = source_id


class FakeRAGService:
    def __init__(self, *args, **kwargs):
        pass

    def index_user_context(self, user):
        return {"indexed": 1, "skipped": 0, "removed": 0}

    def retrieve_chat_context(self, user, query):
        return [{"chunk": FakeChunk("financial_summary", str(user.id)), "similarity": 1.0}]


class FakeLLMService:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def stream_chat_reply(self, context_chunks, history, message):
        FakeLLMService.calls.append(
            {"context_chunks": context_chunks, "history": list(history), "message": message}
        )
        return iter(["Você ", "tem ", "R$ 1.000,00 investidos."])


class UnavailableLLMService(FakeLLMService):
    def stream_chat_reply(self, context_chunks, history, message):
        raise AIServiceUnavailable("Ollama fora do ar.")


@pytest.fixture(autouse=True)
def fake_ai_services(monkeypatch):
    FakeLLMService.calls = []
    monkeypatch.setattr("apps.finance.ai_services.RAGService", FakeRAGService)
    monkeypatch.setattr("apps.finance.ai_services.LLMService", FakeLLMService)


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _consume(response) -> str:
    return b"".join(response.streaming_content).decode("utf-8")


@pytest.mark.django_db
def test_sending_a_message_streams_the_reply_and_persists_both_messages(user):
    response = _client(user).post(
        CHAT_URL, {"message": "Como estão meus investimentos?"}, format="json"
    )

    assert response.status_code == 200
    assert _consume(response) == "Você tem R$ 1.000,00 investidos."

    messages = list(ChatMessage.objects.filter(user=user).order_by("created_at"))
    assert [m.role for m in messages] == [ChatMessageRole.USER, ChatMessageRole.ASSISTANT]
    assert messages[0].content == "Como estão meus investimentos?"
    assert messages[1].content == "Você tem R$ 1.000,00 investidos."
    assert messages[1].sources == [
        {"source_type": "financial_summary", "source_id": str(user.id), "similarity": 1.0}
    ]
    assert messages[0].sources == []


@pytest.mark.django_db
def test_empty_message_returns_400_and_persists_nothing(user):
    response = _client(user).post(CHAT_URL, {"message": "   "}, format="json")

    assert response.status_code == 400
    assert not ChatMessage.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_service_unavailable_returns_503_and_persists_nothing(user, monkeypatch):
    monkeypatch.setattr("apps.finance.ai_services.LLMService", UnavailableLLMService)

    response = _client(user).post(CHAT_URL, {"message": "oi"}, format="json")

    assert response.status_code == 503
    assert not ChatMessage.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_previous_turns_are_sent_as_history_to_the_llm(user):
    _consume(_client(user).post(CHAT_URL, {"message": "primeira pergunta"}, format="json"))

    _consume(_client(user).post(CHAT_URL, {"message": "segunda pergunta"}, format="json"))

    last_call = FakeLLMService.calls[-1]
    assert last_call["message"] == "segunda pergunta"
    assert [m.content for m in last_call["history"]] == [
        "primeira pergunta",
        "Você tem R$ 1.000,00 investidos.",
    ]


@pytest.mark.django_db
def test_get_returns_the_full_history_in_chronological_order(user):
    _consume(_client(user).post(CHAT_URL, {"message": "primeira"}, format="json"))
    _consume(_client(user).post(CHAT_URL, {"message": "segunda"}, format="json"))

    response = _client(user).get(CHAT_URL)

    assert response.status_code == 200
    contents = [m["content"] for m in response.data]
    assert contents == [
        "primeira",
        "Você tem R$ 1.000,00 investidos.",
        "segunda",
        "Você tem R$ 1.000,00 investidos.",
    ]


@pytest.mark.django_db
def test_get_only_returns_the_current_users_messages(user, other_user):
    ChatMessage.objects.create(user=other_user, role=ChatMessageRole.USER, content="do outro")

    response = _client(user).get(CHAT_URL)

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_get_requires_authentication():
    response = APIClient().get(CHAT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_deleting_clears_the_history(user):
    ChatMessage.objects.create(user=user, role=ChatMessageRole.USER, content="oi")

    response = _client(user).delete(CHAT_URL)

    assert response.status_code == 204
    assert not ChatMessage.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_deleting_without_history_returns_404(user):
    response = _client(user).delete(CHAT_URL)

    assert response.status_code == 404


@pytest.mark.django_db
def test_deleting_does_not_affect_another_users_history(user, other_user):
    other_message = ChatMessage.objects.create(
        user=other_user, role=ChatMessageRole.USER, content="do outro"
    )

    response = _client(user).delete(CHAT_URL)

    assert response.status_code == 404
    assert ChatMessage.objects.filter(id=other_message.id).exists()


@pytest.mark.django_db
def test_delete_requires_authentication():
    response = APIClient().delete(CHAT_URL)

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_send_requires_authentication():
    response = APIClient().post(CHAT_URL, {"message": "oi"}, format="json")

    assert response.status_code in (401, 403)
