import graphene

from apps.finance.graphql import Query as FinanceQuery


class Query(FinanceQuery, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query)
