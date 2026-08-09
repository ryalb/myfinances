from rest_framework.pagination import PageNumberPagination


class UnboundedCollectionPagination(PageNumberPagination):
    """Paginacao para colecoes que crescem sem limite: transacoes e sync jobs.

    As outras listas (contas, cartoes, investimentos, previdencia, assinaturas,
    conexoes) tem tamanho naturalmente pequeno e ficam sem paginacao de proposito.
    Ligar paginacao global mudaria a forma da resposta em oito telas -- de lista
    para `{count, next, previous, results}` -- sem ganho nenhum.

    `max_page_size` nao e detalhe: sem teto, `?page_size=999999` derrota a
    paginacao e o cliente volta a puxar a tabela inteira.
    """

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
