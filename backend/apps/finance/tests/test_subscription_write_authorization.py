"""Testes de autorizacao na escrita de assinaturas e pagamentos.

`SubscriptionViewSet` e `SubscriptionPaymentViewSet` sao `ModelViewSet`, e o
`get_queryset` de cada um escopa a leitura ao usuario. Isso protege GET, PATCH e
DELETE de objetos alheios (404), mas nao diz nada sobre as **FKs enviadas no
corpo**: `SubscriptionPayment.subscription`, `Subscription.connection` e
`Subscription.payment_account` eram campos livres do ModelSerializer, aceitando
qualquer id existente no banco.

Sem isto, a UI de escrita deste MVP seria construida sobre um endpoint que permite
gravar dentro dos dados de outro usuario -- e `Subscription.payment_account` aponta
para uma conta bancaria real.
"""

import pytest
from rest_framework.test import APIClient

from apps.finance.models import (
    Account,
    AccountType,
    Connection,
    ConnectionStatus,
    FinancialInstitution,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
)

SUBSCRIPTIONS_URL = "/api/v1/subscriptions/"
PAYMENTS_URL = "/api/v1/subscription-payments/"

WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}


def test_no_write_enabled_viewset_accepts_an_unrestricted_fk():
    """Generalizacao do bug: qualquer viewset com escrita cujo serializer aceite
    uma FK validada contra a tabela inteira deixa gravar dentro do dado de outro
    usuario.

    Roda sem banco -- inspeciona o `where` do queryset, que e lazy. Viewsets
    somente-leitura ficam de fora: sem rota de escrita, a FK nao e exposta.
    """
    from django.contrib.auth import get_user_model
    from rest_framework import serializers as drf
    from rest_framework import viewsets

    from apps.finance import views as views_mod

    class RequestWithUser:
        # Instancia nao salva: tem pk para o filtro montar, sem tocar o banco.
        user = get_user_model()(pk=1, username="auditor")

    offenders = []
    for attr in dir(views_mod):
        viewset = getattr(views_mod, attr)
        if not (isinstance(viewset, type) and issubclass(viewset, viewsets.GenericViewSet)):
            continue
        if not WRITE_ACTIONS & set(dir(viewset)):
            continue
        serializer_class = getattr(viewset, "serializer_class", None)
        if serializer_class is None:
            continue

        fields = serializer_class(context={"request": RequestWithUser()}).fields
        for name, field in fields.items():
            if not isinstance(field, drf.PrimaryKeyRelatedField) or field.read_only:
                continue
            if not field.get_queryset().query.where:
                offenders.append(f"{attr}.{name}")

    assert offenders == [], (
        "FK gravavel validada contra a tabela inteira: "
        f"{', '.join(offenders)}. Use UserScopedPrimaryKeyRelatedField."
    )


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def my_subscription(db, user):
    return Subscription.objects.create(
        user=user,
        name="Minha internet",
        category=SubscriptionCategory.INTERNET,
        amount=120,
        due_day=10,
    )


@pytest.fixture
def their_subscription(db, other_user):
    return Subscription.objects.create(
        user=other_user,
        name="Internet do invasor",
        category=SubscriptionCategory.INTERNET,
        amount=500,
        due_day=15,
    )


@pytest.fixture
def their_connection(db, other_user):
    institution = FinancialInstitution.objects.create(name="Banco do outro", provider_id="777")
    return Connection.objects.create(
        user=other_user,
        institution=institution,
        external_id="item-do-outro",
        status=ConnectionStatus.ACTIVE,
    )


@pytest.fixture
def their_account(db, their_connection):
    return Account.objects.create(
        connection=their_connection,
        external_id="acc-do-outro",
        name="Conta do outro",
        type=AccountType.CHECKING,
        balance=9999,
    )


@pytest.mark.django_db
def test_cannot_create_a_payment_on_someone_elses_subscription(api, their_subscription):
    response = api.post(
        PAYMENTS_URL,
        {"subscription": their_subscription.id, "due_date": "2026-08-10", "status": "paid"},
        format="json",
    )

    assert response.status_code == 400, response.data
    assert not SubscriptionPayment.objects.filter(subscription=their_subscription).exists()


@pytest.mark.django_db
def test_cannot_repoint_an_own_payment_to_someone_elses_subscription(
    api, my_subscription, their_subscription
):
    payment = SubscriptionPayment.objects.create(
        subscription=my_subscription, due_date="2026-08-10", status=SubscriptionStatus.PENDING
    )

    response = api.patch(
        f"{PAYMENTS_URL}{payment.id}/",
        {"subscription": their_subscription.id},
        format="json",
    )

    assert response.status_code == 400, response.data
    payment.refresh_from_db()
    assert payment.subscription_id == my_subscription.id


@pytest.mark.django_db
def test_cannot_attach_a_subscription_to_someone_elses_connection(api, their_connection):
    response = api.post(
        SUBSCRIPTIONS_URL,
        {
            "name": "Tentativa",
            "category": "internet",
            "amount": "10.00",
            "due_day": 5,
            "connection": their_connection.id,
        },
        format="json",
    )

    assert response.status_code == 400, response.data
    assert not Subscription.objects.filter(connection=their_connection).exists()


@pytest.mark.django_db
def test_cannot_attach_a_subscription_to_someone_elses_payment_account(api, their_account):
    response = api.post(
        SUBSCRIPTIONS_URL,
        {
            "name": "Tentativa",
            "category": "internet",
            "amount": "10.00",
            "due_day": 5,
            "payment_account": their_account.id,
        },
        format="json",
    )

    assert response.status_code == 400, response.data
    assert not Subscription.objects.filter(payment_account=their_account).exists()


@pytest.mark.django_db
def test_cannot_repoint_an_own_subscription_to_someone_elses_account(
    api, my_subscription, their_account
):
    response = api.patch(
        f"{SUBSCRIPTIONS_URL}{my_subscription.id}/",
        {"payment_account": their_account.id},
        format="json",
    )

    assert response.status_code == 400, response.data
    my_subscription.refresh_from_db()
    assert my_subscription.payment_account_id is None


@pytest.mark.django_db
def test_own_connection_and_account_are_still_accepted(api, connection, account):
    """A restricao nao pode ser tao larga que quebre o caso legitimo."""
    response = api.post(
        SUBSCRIPTIONS_URL,
        {
            "name": "Conta de luz",
            "category": "utilities",
            "amount": "210.00",
            "due_day": 8,
            "connection": connection.id,
            "payment_account": account.id,
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    created = Subscription.objects.get(pk=response.data["id"])
    assert created.user_id == connection.user_id
    assert created.payment_account_id == account.id


@pytest.mark.django_db
def test_own_payment_can_be_marked_paid(api, my_subscription):
    payment = SubscriptionPayment.objects.create(
        subscription=my_subscription, due_date="2026-08-10", status=SubscriptionStatus.PENDING
    )

    response = api.patch(
        f"{PAYMENTS_URL}{payment.id}/",
        {"status": "paid", "paid_date": "2026-08-11", "paid_amount": "125.40"},
        format="json",
    )

    assert response.status_code == 200, response.data
    payment.refresh_from_db()
    assert payment.status == SubscriptionStatus.PAID
    assert str(payment.paid_amount) == "125.40"


@pytest.mark.django_db
def test_someone_elses_payment_stays_invisible(api, their_subscription):
    payment = SubscriptionPayment.objects.create(
        subscription=their_subscription, due_date="2026-08-15", status=SubscriptionStatus.PENDING
    )

    assert api.get(f"{PAYMENTS_URL}{payment.id}/").status_code == 404
    assert api.delete(f"{PAYMENTS_URL}{payment.id}/").status_code == 404
    assert SubscriptionPayment.objects.filter(pk=payment.id).exists()


@pytest.mark.django_db
def test_manual_paid_survives_the_next_reconciliation(user, my_subscription):
    """O ponto da marcacao manual e justamente a conta que nao vem de instituicao
    conectada: se o sync seguinte reverter para pendente, o recurso nao serve."""
    from apps.finance.tasks import _reconcile_subscriptions

    payment = SubscriptionPayment.objects.create(
        subscription=my_subscription,
        due_date="2026-08-10",
        status=SubscriptionStatus.PAID,
        paid_date="2026-08-10",
        paid_amount=120,
    )

    _reconcile_subscriptions(user)

    payment.refresh_from_db()
    assert payment.status == SubscriptionStatus.PAID


@pytest.mark.django_db
@pytest.mark.parametrize("due_day", [0, 32, 99])
def test_due_day_outside_the_calendar_is_rejected(api, due_day):
    """`_due_date_for` cai no dia 28 quando a data e invalida, entao um due_day
    fora de 1-31 nao estoura: vira silenciosamente outro vencimento. Com input de
    usuario isso precisa parar na borda."""
    response = api.post(
        SUBSCRIPTIONS_URL,
        {"name": "Tentativa", "category": "other", "amount": "10.00", "due_day": due_day},
        format="json",
    )

    assert response.status_code == 400, response.data
    assert "due_day" in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("due_day", [1, 15, 31])
def test_valid_due_day_is_accepted(api, due_day):
    response = api.post(
        SUBSCRIPTIONS_URL,
        {"name": "Valida", "category": "other", "amount": "10.00", "due_day": due_day},
        format="json",
    )

    assert response.status_code == 201, response.data
