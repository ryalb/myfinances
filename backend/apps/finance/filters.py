"""Filtros da tela de transacoes.

Compartilhado entre a listagem (`TransactionViewSet`) e a exportacao CSV. Dois
lugares aplicando os mesmos filtros divergem com o tempo, e o sintoma seria um CSV
que nao corresponde ao que esta na tela -- silencioso e chato de descobrir.
"""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Transaction


def user_transactions(user):
    """Transacoes do usuario, por conta ou por cartao.

    `Transaction` nao tem FK para `Connection`: pertence a uma conta **ou** a um
    cartao, entao o escopo por usuario passa pelos dois caminhos.
    """
    return Transaction.objects.filter(
        Q(account__connection__user=user) | Q(card__connection__user=user)
    )


def _as_decimal(raw):
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _aware_midnight(raw_date: str):
    """Meia-noite do dia informado, no fuso ativo.

    `booked_at` e DateTimeField; passar a string "YYYY-MM-DD" ou um `date` cru
    pro filtro faz o Django promover para meia-noite **naive** e emitir
    RuntimeWarning (e assumir UTC) a cada request. Retorna None para string
    invalida, para o chamador ignorar o filtro em vez de estourar.
    """
    parsed = parse_date(raw_date)
    if parsed is None:
        return None
    return timezone.make_aware(datetime.combine(parsed, time.min))


def filter_transactions(queryset, params):
    """Aplica os filtros suportados, ignorando parametro vazio ou invalido.

    Ignorar em vez de responder 400: um filtro digitado errado na URL nao deve
    derrubar a tela, e o conjunto sem o filtro e um resultado honesto.
    """
    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(description__icontains=search)

    category = (params.get("category") or "").strip()
    if category:
        # `__iexact` e nao `__icontains`: a lista do filtro vem de valores
        # existentes, entao "Clothing" nao deve arrastar "Clothing rental".
        queryset = queryset.filter(category__iexact=category)

    tx_type = (params.get("type") or "").strip().lower()
    if tx_type in ("credit", "debit"):
        queryset = queryset.filter(type=tx_type)

    account = (params.get("account") or "").strip()
    if account.isdigit():
        queryset = queryset.filter(account_id=int(account))

    card = (params.get("card") or "").strip()
    if card.isdigit():
        queryset = queryset.filter(card_id=int(card))

    start_date = (params.get("start_date") or "").strip()
    if start_date:
        start_at = _aware_midnight(start_date)
        if start_at is not None:
            queryset = queryset.filter(booked_at__gte=start_at)

    end_date = (params.get("end_date") or "").strip()
    if end_date:
        end_at = _aware_midnight(end_date)
        if end_at is not None:
            queryset = queryset.filter(booked_at__lt=end_at)

    min_amount = _as_decimal(params.get("min_amount"))
    if min_amount is not None:
        queryset = queryset.filter(amount__gte=min_amount)

    max_amount = _as_decimal(params.get("max_amount"))
    if max_amount is not None:
        queryset = queryset.filter(amount__lte=max_amount)

    return queryset
