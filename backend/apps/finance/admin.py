from django.contrib import admin

from .models import (
    Account,
    Card,
    CategorizationRule,
    Connection,
    FinancialGoal,
    FinancialInstitution,
    Investment,
    InvestmentPosition,
    InvestmentTransaction,
    MarketIndexRate,
    MarketQuote,
    NetWorthSnapshot,
    PensionPlan,
    SyncJob,
    Transaction,
)

admin.site.register(FinancialInstitution)
admin.site.register(Connection)
admin.site.register(Account)
admin.site.register(Card)
admin.site.register(Transaction)
admin.site.register(Investment)
admin.site.register(InvestmentPosition)
admin.site.register(InvestmentTransaction)
admin.site.register(PensionPlan)
admin.site.register(NetWorthSnapshot)
admin.site.register(FinancialGoal)
admin.site.register(SyncJob)
admin.site.register(CategorizationRule)
admin.site.register(MarketIndexRate)
admin.site.register(MarketQuote)
