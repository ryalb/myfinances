"""Testes do endpoint HTTP /graphql/.

Estes testes existem porque os outros nao cobriam o que quebrou em producao.
`test_graphql_schema.py` chama `schema.execute()` direto, com `request.user`
atribuido a mao -- isso valida resolver, e nao passa perto da camada HTTP. O
resultado foi um schema inteiro correto atras de um endpoint que respondia 403 a
todo POST do navegador.

Dois pontos exigem cuidado no proprio teste:

- `Client()` do Django **desliga CSRF por padrao**. Sem `enforce_csrf_checks=True` o
  teste passaria com o bug presente.
- O header Authorization e ignorado pelo `AuthenticationMiddleware`. Um teste que
  so verifica status 200 nao detecta "autenticado como anonimo", porque o GraphQL
  devolve 200 com dados vazios.
"""

import pytest
from django.test import Client
from rest_framework_simplejwt.tokens import AccessToken

from apps.finance.models import Subscription, SubscriptionCategory

URL = "/graphql/"
QUERY = '{"query": "{ subscriptions { name } }"}'


@pytest.fixture
def csrf_client():
    """Cliente que realmente aplica CSRF, ao contrario do default."""
    return Client(enforce_csrf_checks=True)


def post(client, body=QUERY, token=None):
    headers = {"content_type": "application/json"}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client.post(URL, data=body, **headers)


@pytest.fixture
def subscription(db, user):
    return Subscription.objects.create(
        user=user,
        name="Netflix",
        category=SubscriptionCategory.STREAMING,
        amount=55,
        due_day=10,
    )


@pytest.mark.django_db
def test_post_without_csrf_token_is_not_rejected(csrf_client):
    """A API autentica por Bearer no header, nao por cookie de sessao: nao existe
    token de CSRF a enviar. Exigir um so bloqueava o cliente legitimo."""
    response = post(csrf_client)

    assert response.status_code != 403, "CSRF voltou a bloquear o endpoint"
    assert response.status_code == 200


@pytest.mark.django_db
def test_bearer_token_authenticates_the_request(csrf_client, user, subscription):
    """O caso que faltava: `request.user` vinha do middleware de sessao, que ignora
    o header Authorization -- todo resolver via anonimo e devolvia vazio, com 200."""
    token = str(AccessToken.for_user(user))

    response = post(csrf_client, token=token)

    assert response.status_code == 200, response.content
    assert response.json()["data"]["subscriptions"] == [{"name": "Netflix"}]


@pytest.mark.django_db
def test_without_a_token_the_data_comes_back_empty(csrf_client, subscription):
    response = post(csrf_client)

    assert response.status_code == 200
    assert response.json()["data"]["subscriptions"] == []


@pytest.mark.django_db
def test_invalid_token_returns_401(csrf_client, subscription):
    """401 e nao 200-com-vazio: token expirado tratado como "usuario sem dados"
    faria o cliente mostrar dashboard zerado em vez de renovar a sessao."""
    response = post(csrf_client, token="isto-nao-e-um-jwt")

    assert response.status_code == 401, response.content


@pytest.mark.django_db
def test_expired_token_returns_401(csrf_client, user, subscription):
    from datetime import timedelta

    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(seconds=-10))

    response = post(csrf_client, token=str(token))

    assert response.status_code == 401, response.content


@pytest.mark.django_db
def test_another_users_token_never_sees_this_users_data(csrf_client, other_user, subscription):
    token = str(AccessToken.for_user(other_user))

    response = post(csrf_client, token=token)

    assert response.status_code == 200
    assert response.json()["data"]["subscriptions"] == []


@pytest.mark.django_db
def test_the_dashboard_queries_all_resolve_over_http(csrf_client, user, connection, account):
    """Varredura das consultas que o frontend realmente dispara. Cada uma passou a
    existir num commit diferente, e nenhuma tinha cobertura HTTP."""
    token = str(AccessToken.for_user(user))
    queries = {
        "financialSummary": "{ financialSummary { netWorth } }",
        "monthlyCashFlow": "{ monthlyCashFlow { income expenses } }",
        "netWorthHistory": "{ netWorthHistory { netWorth } }",
        "investmentDistribution": "{ investmentDistribution { label value } }",
        "financialFreedomProjection": "{ financialFreedomProjection { currentNetWorth } }",
        "subscriptionOverview": "{ subscriptionOverview { monthlyRecurringTotal } }",
        "alerts": "{ alerts { kind severity } }",
        "futureProjection": "{ futureProjection { currentNetWorth } }",
        "financialHealthScore": "{ financialHealthScore { score } }",
    }

    for name, query in queries.items():
        import json

        response = post(csrf_client, body=json.dumps({"query": query}), token=token)
        assert response.status_code == 200, f"{name}: {response.status_code} {response.content}"
        payload = response.json()
        assert "errors" not in payload, f"{name}: {payload['errors']}"
        assert payload["data"][name] is not None, f"{name} devolveu null autenticado"
