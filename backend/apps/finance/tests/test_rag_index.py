"""Testes do indice RAG: chunking por dominio, upsert e busca vetorial.

Tres defeitos motivam este arquivo, todos observados no codigo anterior:

1. `index_user_context` fazia `DocumentChunk.objects.create()` a cada chamada, e a
   view chamava a cada POST -- o indice duplicava a cada relatorio gerado.
2. Existia um unico chunk (`financial_summary`) com todo o contexto, o que torna
   `top_k` inutil: os 5 resultados eram a mesma coisa.
3. A similaridade era cosseno em Python varrendo todos os chunks; o pgvector
   estava na imagem do Postgres e nao era usado.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.finance.ai_services import (
    SUMMARY_SOURCE_TYPE,
    AIServiceUnavailable,
    Document,
    RAGService,
    _format_amount,
    build_user_documents,
)
from apps.finance.models import (
    EMBEDDING_DIMENSIONS,
    Card,
    CategorizationRule,
    DocumentChunk,
    DocumentChunkStatus,
    Embedding,
    FinancialGoal,
    Investment,
    InvestmentPosition,
    MarketIndexKind,
    MarketIndexRate,
    MarketQuote,
    Subscription,
    SubscriptionCategory,
    Transaction,
    TransactionType,
)


class FakeOllama:
    """Embeddings deterministicos sem rede.

    O vetor deriva do texto para que conteudos diferentes tenham vetores
    diferentes, o que e o suficiente para os testes de indexacao.
    """

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS):
        self.dimensions = dimensions
        self.calls: list[str] = []

    def __call__(self, text: str) -> list[float]:
        self.calls.append(text)
        seed = sum(ord(char) for char in text) or 1
        return [((seed + i) % 97) / 97 for i in range(self.dimensions)]


@pytest.fixture
def rag(monkeypatch):
    service = RAGService()
    fake = FakeOllama()
    monkeypatch.setattr(service, "_get_embedding", fake)
    service.fake = fake
    return service


# --------------------------------------------------------------------------
# Chunking por dominio
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_summary_document_is_always_present_even_with_no_data(user):
    documents = build_user_documents(user)

    assert [doc.source_type for doc in documents] == [SUMMARY_SOURCE_TYPE]


@pytest.mark.django_db
def test_domains_without_data_are_omitted(user, connection, account):
    """Um chunk "Cartoes (0)" nao responde nada e ainda concorre na busca."""
    types = {doc.source_type for doc in build_user_documents(user)}

    assert "accounts" in types
    assert "cards" not in types
    assert "goals" not in types


@pytest.mark.django_db
def test_market_rates_document_is_omitted_when_no_rate_synced(user):
    types = {doc.source_type for doc in build_user_documents(user)}

    assert "market_rates" not in types


@pytest.mark.django_db
def test_market_rates_document_shows_the_latest_point_per_index(user):
    MarketIndexRate.objects.create(
        kind=MarketIndexKind.SELIC, reference_date=date(2026, 7, 1), value=Decimal("0.036523")
    )
    MarketIndexRate.objects.create(
        kind=MarketIndexKind.SELIC, reference_date=date(2026, 7, 2), value=Decimal("0.036789")
    )
    MarketIndexRate.objects.create(
        kind=MarketIndexKind.IPCA, reference_date=date(2026, 6, 1), value=Decimal("0.50")
    )

    documents = [doc for doc in build_user_documents(user) if doc.source_type == "market_rates"]

    assert len(documents) == 1
    content = documents[0].content
    assert "Selic" in content and "0.036789" in content and "2026-07-02" in content
    assert "0.036523" not in content, "so o ponto mais recente de cada indice deve aparecer"
    assert "IPCA" in content and "0.50" in content


@pytest.mark.django_db
def test_market_quotes_document_is_omitted_without_held_tickers(user):
    types = {doc.source_type for doc in build_user_documents(user)}

    assert "market_quotes" not in types


@pytest.mark.django_db
def test_market_quotes_document_is_omitted_when_ticker_has_no_quote_yet(user, connection):
    Investment.objects.create(
        connection=connection, external_id="i1", name="PMLL11", kind="EQUITY", code="PMLL11"
    )

    types = {doc.source_type for doc in build_user_documents(user)}

    assert "market_quotes" not in types


@pytest.mark.django_db
def test_market_quotes_document_shows_only_the_users_own_tickers(user, connection):
    Investment.objects.create(
        connection=connection, external_id="i1", name="PMLL11", kind="EQUITY", code="PMLL11"
    )
    MarketQuote.objects.create(
        ticker="PMLL11", as_of_date=date(2026, 8, 30), price=Decimal("102.65"),
        dividend_yield=Decimal("11.70"),
    )
    # Cotacao de um ticker que o usuario nao possui: nao deve aparecer.
    MarketQuote.objects.create(
        ticker="BTLG11", as_of_date=date(2026, 8, 30), price=Decimal("99.45"),
    )

    documents = [doc for doc in build_user_documents(user) if doc.source_type == "market_quotes"]

    assert len(documents) == 1
    content = documents[0].content
    assert "PMLL11" in content and "102,65" in content and "11.70%" in content
    assert "BTLG11" not in content


@pytest.mark.django_db
def test_market_quotes_document_ignores_fixed_income_codes(user, connection):
    """`Investment.code` de renda fixa pode ser um CNPJ ou codigo de
    debenture/CRA, nunca um ticker -- nao deve nem entrar na busca de cotacao.
    Ver `market_data.held_tickers` e `TRADABLE_DISPLAY_CATEGORIES`."""
    Investment.objects.create(
        connection=connection,
        external_id="i1",
        name="CRA XPTO",
        kind="FIXED_INCOME",
        code="CRA024002ML",
    )

    types = {doc.source_type for doc in build_user_documents(user)}

    assert "market_quotes" not in types


@pytest.mark.django_db
def test_each_domain_becomes_its_own_document(user, connection, account):
    Card.objects.create(
        connection=connection, external_id="card-1", name="Cartao", credit_limit=5000
    )
    FinancialGoal.objects.create(user=user, name="Reserva", target_amount=10000)
    CategorizationRule.objects.create(user=user, pattern="uber", category="transporte")
    Subscription.objects.create(
        user=user,
        name="Internet",
        category=SubscriptionCategory.INTERNET,
        amount=120,
        due_day=10,
    )

    types = {doc.source_type for doc in build_user_documents(user)}

    assert {
        SUMMARY_SOURCE_TYPE,
        "accounts",
        "cards",
        "goals",
        "categorization_rules",
        "subscriptions",
        "sync_history",
    } <= types


@pytest.mark.django_db
def test_transactions_are_chunked_one_document_per_month(user, account):
    for day, month in ((5, 7), (20, 7), (3, 8)):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-{month}-{day}",
            description="Mercado",
            amount=Decimal("100.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.make_aware(timezone.datetime(timezone.localdate().year, month, day)),
        )

    documents = [doc for doc in build_user_documents(user) if doc.source_type == "transactions"]

    assert len(documents) == 2, "esperava um documento por mes"
    assert {doc.source_id for doc in documents} == {
        f"{timezone.localdate().year}-07",
        f"{timezone.localdate().year}-08",
    }


@pytest.mark.django_db
def test_document_content_is_scoped_to_the_user(user, other_user, connection, account):
    from apps.finance.models import (
        Account,
        AccountType,
        Connection,
        ConnectionStatus,
        FinancialInstitution,
    )

    other_institution = FinancialInstitution.objects.create(name="Outro", provider_id="888")
    other_connection = Connection.objects.create(
        user=other_user,
        institution=other_institution,
        external_id="item-outro-rag",
        status=ConnectionStatus.ACTIVE,
    )
    Account.objects.create(
        connection=other_connection,
        external_id="acc-outro-rag",
        name="Conta secreta do outro",
        type=AccountType.CHECKING,
        balance=99999,
    )

    blob = "\n".join(doc.content for doc in build_user_documents(user))

    assert "Conta secreta do outro" not in blob


# --------------------------------------------------------------------------
# Formatacao de moeda no padrao brasileiro
# --------------------------------------------------------------------------


def test_format_amount_uses_brazilian_separators():
    assert _format_amount(Decimal("334106.25")) == "R$ 334.106,25"


def test_format_amount_appends_currency_code_when_not_brl():
    assert _format_amount(Decimal("100.5"), "USD") == "100,50 USD"


@pytest.mark.django_db
def test_account_document_formats_balance_in_brazilian_currency(user, connection, account):
    account.balance = Decimal("180149.30")
    account.available_balance = Decimal("180149.30")
    account.save()

    document = next(doc for doc in build_user_documents(user) if doc.source_type == "accounts")

    assert "R$ 180.149,30" in document.content
    assert "180149.3" not in document.content


# --------------------------------------------------------------------------
# Performance e distribuicao de investimentos
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_investments_document_reports_quota_variation_across_positions(user, connection):
    """O usuario quer saber se os fundos estao com performance boa -- sem
    comparar duas datas, a LLM so tinha a foto do dia, nunca a tendencia."""
    investment = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Fundo XP", kind="MUTUAL_FUND"
    )
    InvestmentPosition.objects.create(
        investment=investment,
        as_of_date=date(2026, 6, 1),
        quantity=100,
        unit_price=Decimal("100.00"),
        market_value=Decimal("10000.00"),
    )
    InvestmentPosition.objects.create(
        investment=investment,
        as_of_date=date(2026, 8, 1),
        quantity=100,
        unit_price=Decimal("103.00"),
        market_value=Decimal("10300.00"),
    )

    document = next(doc for doc in build_user_documents(user) if doc.source_type == "investments")

    assert "variacao de +3.00%" in document.content
    assert "2026-06-01" in document.content


@pytest.mark.django_db
def test_investments_document_reports_distribution_by_kind(user, connection):
    """Sinal direto de concentracao de risco pra LLM sugerir diversificacao."""
    fund = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Fundo XP", kind="MUTUAL_FUND"
    )
    fii = Investment.objects.create(
        connection=connection, external_id="inv-2", name="FII Tijolo", kind="FII"
    )
    InvestmentPosition.objects.create(
        investment=fund, as_of_date=date.today(), market_value=Decimal("8000.00")
    )
    InvestmentPosition.objects.create(
        investment=fii, as_of_date=date.today(), market_value=Decimal("2000.00")
    )

    document = next(doc for doc in build_user_documents(user) if doc.source_type == "investments")

    assert "MUTUAL_FUND: R$ 8.000,00 (80.0% da carteira)" in document.content
    assert "FII: R$ 2.000,00 (20.0% da carteira)" in document.content


@pytest.mark.django_db
def test_investments_document_skips_performance_with_a_single_position(user, connection):
    investment = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Fundo XP", kind="MUTUAL_FUND"
    )
    InvestmentPosition.objects.create(
        investment=investment,
        as_of_date=date.today(),
        unit_price=Decimal("100.00"),
        market_value=Decimal("10000.00"),
    )

    document = next(doc for doc in build_user_documents(user) if doc.source_type == "investments")

    assert "variacao" not in document.content


def test_digest_changes_with_content():
    a = Document(source_type="accounts", source_id="1", content="saldo 100")
    b = Document(source_type="accounts", source_id="1", content="saldo 200")

    assert a.digest != b.digest
    assert a.digest == Document(source_type="accounts", source_id="1", content="saldo 100").digest


@pytest.mark.django_db
def test_transaction_chunking_cost_does_not_grow_with_volume(user, account):
    """As somas saem do banco: o custo em queries nao pode depender de quantos
    meses ou lancamentos existem."""
    from django.db import connection as db_connection
    from django.test.utils import CaptureQueriesContext

    from apps.finance.ai_services import _build_transaction_documents

    def count_queries_for(n: int) -> int:
        Transaction.objects.all().delete()
        for i in range(n):
            month = (i % 5) + 1
            Transaction.objects.create(
                account=account,
                external_id=f"tx-cost-{i}",
                description=f"Lancamento {i}",
                amount=Decimal("10.00") + i,
                type=TransactionType.DEBIT if i % 2 else TransactionType.CREDIT,
                booked_at=timezone.make_aware(
                    timezone.datetime(timezone.localdate().year, month, (i % 27) + 1)
                ),
            )
        with CaptureQueriesContext(db_connection) as ctx:
            _build_transaction_documents(user, months=12)
        return len(ctx)

    with_10 = count_queries_for(10)
    with_60 = count_queries_for(60)

    assert with_10 == with_60, f"custo cresceu com o volume: {with_10} -> {with_60}"
    assert with_10 <= 3, f"esperava 3 queries fixas, foram {with_10}"


# --------------------------------------------------------------------------
# Upsert
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_reindexing_does_not_duplicate_chunks(rag, user, connection, account):
    rag.index_user_context(user)
    first_count = DocumentChunk.objects.filter(user=user).count()

    rag.index_user_context(user)
    rag.index_user_context(user)

    assert DocumentChunk.objects.filter(user=user).count() == first_count
    assert Embedding.objects.filter(chunk__user=user).count() == first_count


@pytest.mark.django_db
def test_unchanged_content_is_not_reembedded(rag, user, connection, account):
    rag.index_user_context(user)
    calls_after_first = len(rag.fake.calls)

    stats = rag.index_user_context(user)

    assert stats["indexed"] == 0
    assert stats["skipped"] > 0
    assert len(rag.fake.calls) == calls_after_first, "reembedou conteudo inalterado"


@pytest.mark.django_db
def test_changed_content_is_reembedded(rag, user, connection, account):
    rag.index_user_context(user)
    calls_after_first = len(rag.fake.calls)

    account.balance = Decimal("54321.00")
    account.save()
    stats = rag.index_user_context(user)

    assert stats["indexed"] > 0
    assert len(rag.fake.calls) > calls_after_first


@pytest.mark.django_db
def test_chunk_embedded_by_another_model_is_reindexed(rag, user, connection, account, monkeypatch):
    """Vetor de outro modelo vive em outro espaco: comparar daria similaridade
    sem significado."""
    rag.index_user_context(user)

    Embedding.objects.filter(chunk__user=user).update(model="outro-modelo")
    stats = rag.index_user_context(user)

    assert stats["indexed"] > 0
    assert stats["skipped"] == 0


@pytest.mark.django_db
def test_domain_that_disappeared_is_removed_from_the_index(rag, user, connection, account):
    card = Card.objects.create(
        connection=connection, external_id="card-1", name="Cartao", credit_limit=5000
    )
    rag.index_user_context(user)
    assert DocumentChunk.objects.filter(user=user, source_type="cards").exists()

    card.delete()
    rag.index_user_context(user)

    assert not DocumentChunk.objects.filter(
        user=user, source_type="cards"
    ).exists(), "a LLM citaria um cartao que nao existe mais"


@pytest.mark.django_db
def test_index_is_scoped_per_user(rag, user, other_user, connection, account):
    rag.index_user_context(user)

    assert DocumentChunk.objects.filter(user=user).exists()
    assert not DocumentChunk.objects.filter(user=other_user).exists()


# --------------------------------------------------------------------------
# Busca vetorial
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_returns_chunks_ordered_by_similarity(rag, user, connection, account):
    Card.objects.create(
        connection=connection, external_id="card-1", name="Cartao", credit_limit=5000
    )
    rag.index_user_context(user)

    results = rag.search(user, "cartao de credito", top_k=3)

    assert results, "a busca nao devolveu nada"
    similarities = [item["similarity"] for item in results]
    assert similarities == sorted(similarities, reverse=True)


@pytest.mark.django_db
def test_search_can_filter_by_domain(rag, user, connection, account):
    Card.objects.create(
        connection=connection, external_id="card-1", name="Cartao", credit_limit=5000
    )
    rag.index_user_context(user)

    results = rag.search(user, "qualquer coisa", top_k=5, source_types=["cards"])

    assert [item["chunk"].source_type for item in results] == ["cards"]


@pytest.mark.django_db
def test_search_never_crosses_users(rag, user, other_user, connection, account):
    rag.index_user_context(user)

    assert rag.search(other_user, "patrimonio", top_k=5) == []


@pytest.mark.django_db
def test_search_ignores_chunks_not_indexed(rag, user, connection, account):
    rag.index_user_context(user)
    DocumentChunk.objects.filter(user=user).update(status=DocumentChunkStatus.PENDING)

    assert rag.search(user, "patrimonio", top_k=5) == []


@pytest.mark.django_db
def test_report_context_always_includes_the_summary(rag, user, connection, account):
    """O resumo perderia a disputa de similaridade contra um mes de transacoes,
    que tem muito mais texto sobre qualquer assunto especifico."""
    for day in range(1, 20):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-{day}",
            description="Compra relevante de investimento e patrimonio",
            amount=Decimal("100.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.now(),
        )
    rag.index_user_context(user)

    context = rag.retrieve_report_context(user, "investimentos", top_k=2)

    assert context[0]["chunk"].source_type == SUMMARY_SOURCE_TYPE
    types = [item["chunk"].source_type for item in context]
    assert types.count(SUMMARY_SOURCE_TYPE) == 1, "resumo duplicado no contexto"


@pytest.mark.django_db
def test_report_context_always_includes_investments(rag, user, connection, account):
    """Avaliar performance da carteira e sugerir aportes e o pedido mais comum
    deste relatorio -- sem ancorar, o documento dependia da sorte da busca
    semantica contra meses de transacoes."""
    investment = Investment.objects.create(
        connection=connection, external_id="inv-1", name="Fundo XP", kind="MUTUAL_FUND"
    )
    InvestmentPosition.objects.create(
        investment=investment, as_of_date=date.today(), market_value=Decimal("1000.00")
    )
    for day in range(1, 20):
        Transaction.objects.create(
            account=account,
            external_id=f"tx-inv-{day}",
            description="Compra no mercado",
            amount=Decimal("100.00"),
            type=TransactionType.DEBIT,
            booked_at=timezone.now(),
        )
    rag.index_user_context(user)

    context = rag.retrieve_report_context(user, "gastos do mes", top_k=2)

    types = [item["chunk"].source_type for item in context]
    assert types.count("investments") == 1


# --------------------------------------------------------------------------
# Falhas da dependencia local
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_wrong_embedding_dimension_fails_with_a_clear_message(user, monkeypatch):
    """Sem esta checagem o erro apareceria como falha de insercao do Postgres,
    sem dizer que o modelo e o problema."""
    service = RAGService()

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"embedding": [0.1, 0.2, 0.3]}

    monkeypatch.setattr("apps.finance.ai_services.requests.post", lambda *a, **k: Response())

    with pytest.raises(AIServiceUnavailable, match="dimensoes"):
        service._get_embedding("qualquer texto")


@pytest.mark.django_db
def test_ollama_offline_raises_service_unavailable(user, monkeypatch):
    import requests

    service = RAGService()

    def explode(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("apps.finance.ai_services.requests.post", explode)

    with pytest.raises(AIServiceUnavailable, match="embeddings"):
        service._get_embedding("qualquer texto")
