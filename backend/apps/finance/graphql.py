import math

import graphene
from django.utils import timezone
from graphene_django import DjangoObjectType

from .alerts import build_user_alerts
from .consolidation import (
    add_months,
    build_monthly_cash_flow,
    build_recent_month_averages,
    build_subscription_overview,
    build_user_financial_summary,
)
from .models import (
    Account,
    CategorizationRule,
    FinancialInstitution,
    Identity,
    Investment,
    InvestmentPosition,
    NetWorthSnapshot,
    PensionPlan,
    Subscription,
    SubscriptionPayment,
)


class FinancialInstitutionType(DjangoObjectType):
    class Meta:
        model = FinancialInstitution
        fields = ("id", "name", "provider_id", "logo_url")


class IdentityType(DjangoObjectType):
    class Meta:
        model = Identity
        fields = (
            "id",
            "full_name",
            "document",
            "document_type",
            "birth_date",
            "job_title",
            "email",
            "phone_number",
            "address",
        )


class AccountType(DjangoObjectType):
    identity = graphene.Field(IdentityType)

    class Meta:
        model = Account
        fields = ("id", "name", "type", "currency", "balance", "available_balance")

    def resolve_identity(self, info):
        return getattr(self.connection, "identity", None)


class NetWorthSnapshotType(DjangoObjectType):
    class Meta:
        model = NetWorthSnapshot
        fields = ("id", "date", "assets", "liabilities", "net_worth")


class FinancialSummaryBreakdownType(graphene.ObjectType):
    cash = graphene.Float()
    investments = graphene.Float()
    pension = graphene.Float()
    debts = graphene.Float()
    credit_cards = graphene.Float()


class FinancialSummaryType(graphene.ObjectType):
    assets = graphene.Float()
    liabilities = graphene.Float()
    net_worth = graphene.Float()
    breakdown = graphene.Field(FinancialSummaryBreakdownType)


class MonthlyCashFlowType(graphene.ObjectType):
    year = graphene.Int()
    month = graphene.Int()
    income = graphene.Float()
    expenses = graphene.Float()
    savings = graphene.Float()
    savings_rate = graphene.Float()


class FinancialFreedomProjectionType(graphene.ObjectType):
    current_net_worth = graphene.Float()
    monthly_savings = graphene.Float()
    average_monthly_expenses = graphene.Float()
    target_net_worth = graphene.Float()
    estimated_passive_income = graphene.Float()
    financial_runway_months = graphene.Int()
    estimated_retire_date = graphene.String()
    months_to_freedom = graphene.Int()
    target_reached = graphene.Boolean()
    conservative_months = graphene.Int()
    base_months = graphene.Int()
    aggressive_months = graphene.Int()


class InvestmentDistributionItemType(graphene.ObjectType):
    label = graphene.String()
    value = graphene.Float()
    percentage = graphene.Float()


class PensionPlanType(DjangoObjectType):
    is_manual = graphene.Boolean()

    class Meta:
        model = PensionPlan
        fields = ("id", "name", "provider", "balance")

    def resolve_is_manual(self, info):
        return self.connection_id is None


class InvestmentType(DjangoObjectType):
    class Meta:
        model = Investment
        fields = ("id", "name", "kind", "currency")


class InvestmentPositionType(DjangoObjectType):
    # Float, nao o Decimal cru do model: o resto do schema expoe valores
    # monetarios como Float (ver FinancialSummaryType etc.), e o graphene-django
    # serializa DecimalField como string por padrao.
    market_value = graphene.Float()

    class Meta:
        model = InvestmentPosition
        fields = ("id", "investment", "as_of_date", "quantity", "unit_price", "market_value")

    def resolve_market_value(self, info):
        return float(self.market_value)


class SubscriptionType(DjangoObjectType):
    class Meta:
        model = Subscription
        fields = (
            "id",
            "name",
            "category",
            "amount",
            "due_day",
            "is_active",
            "created_at",
            "updated_at",
        )


class SubscriptionPaymentType(DjangoObjectType):
    class Meta:
        model = SubscriptionPayment
        fields = (
            "id",
            "due_date",
            "paid_date",
            "status",
            "paid_amount",
            "created_at",
            "updated_at",
        )


class CategorizationRuleType(DjangoObjectType):
    class Meta:
        model = CategorizationRule
        fields = ("id", "pattern", "category", "priority", "is_active", "created_at", "updated_at")


class SubscriptionScheduleItemType(graphene.ObjectType):
    name = graphene.String()
    category = graphene.String()
    due_date = graphene.String()
    amount = graphene.Float()
    status = graphene.String()


class SubscriptionOverviewType(graphene.ObjectType):
    monthly_recurring_total = graphene.Float()
    active_count = graphene.Int()
    paid_this_month = graphene.Float()
    pending_this_month = graphene.Float()
    overdue_total = graphene.Float()
    overdue = graphene.List(SubscriptionScheduleItemType)
    upcoming = graphene.List(SubscriptionScheduleItemType)


class AlertType(graphene.ObjectType):
    kind = graphene.String()
    severity = graphene.String()
    title = graphene.String()
    detail = graphene.String()
    action_path = graphene.String()


def _request_cached(info, key, factory):
    """Memoiza um calculo pelo tempo de vida da requisicao.

    O dashboard consulta `financialSummary` e `financialFreedomProjection` na mesma
    query, e os dois recalculavam o resumo patrimonial do zero -- iterando as contas
    duas vezes por carga de tela.

    Escopo de requisicao e nao Redis de proposito: e o unico nivel que nao precisa
    de invalidacao. Cache de saldo com invalidacao errada mostra dinheiro errado, o
    que e pior que mostrar devagar.
    """
    cache = getattr(info.context, "_finance_resolver_cache", None)
    if cache is None:
        cache = {}
        info.context._finance_resolver_cache = cache
    if key not in cache:
        cache[key] = factory()
    return cache[key]


class Query(graphene.ObjectType):
    institutions = graphene.List(FinancialInstitutionType)

    accounts = graphene.List(AccountType)
    net_worth_history = graphene.List(NetWorthSnapshotType)
    financial_summary = graphene.Field(FinancialSummaryType)
    monthly_cash_flow = graphene.Field(
        MonthlyCashFlowType, year=graphene.Int(), month=graphene.Int()
    )
    investment_distribution = graphene.List(InvestmentDistributionItemType)
    financial_freedom_projection = graphene.Field(FinancialFreedomProjectionType)
    # Um resolver sem o campo declarado aqui e ignorado em silencio por graphene:
    # nao ha erro de import nem de execucao, o campo so nao entra no schema.
    # test_graphql_schema.py trava a lista completa por causa disso.
    subscriptions = graphene.List(SubscriptionType)
    subscription_payments = graphene.List(SubscriptionPaymentType, subscription_id=graphene.Int())
    categorization_rules = graphene.List(CategorizationRuleType)
    pension_plans = graphene.List(PensionPlanType)
    investment_positions = graphene.List(InvestmentPositionType, investment_id=graphene.Int())
    subscription_overview = graphene.Field(SubscriptionOverviewType, upcoming_days=graphene.Int())
    alerts = graphene.List(AlertType)

    def resolve_institutions(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return FinancialInstitution.objects.none()
        return FinancialInstitution.objects.all().order_by("name")

    def resolve_accounts(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return Account.objects.none()
        return (
            Account.objects.filter(connection__user=user)
            .select_related("connection", "connection__identity")
            .order_by("name")
        )

    def resolve_net_worth_history(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return NetWorthSnapshot.objects.none()
        return NetWorthSnapshot.objects.filter(user=user).order_by("-date")

    def resolve_financial_summary(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return None
        data = _request_cached(
            info, "financial_summary", lambda: build_user_financial_summary(user)
        )
        breakdown = data["breakdown"]
        return FinancialSummaryType(
            assets=float(data["assets"]),
            liabilities=float(data["liabilities"]),
            net_worth=float(data["net_worth"]),
            breakdown=FinancialSummaryBreakdownType(
                cash=float(breakdown["cash"]),
                investments=float(breakdown["investments"]),
                pension=float(breakdown["pension"]),
                debts=float(breakdown["debts"]),
                credit_cards=float(breakdown["credit_cards"]),
            ),
        )

    def resolve_monthly_cash_flow(self, info, year=None, month=None):
        user = info.context.user
        if not user or not user.is_authenticated:
            return None
        now = timezone.localdate()
        current_year = now.year
        current_month = now.month
        data = build_monthly_cash_flow(
            user, year=year or current_year, month=month or current_month
        )
        return MonthlyCashFlowType(
            year=data["year"],
            month=data["month"],
            income=float(data["income"]),
            expenses=float(data["expenses"]),
            savings=float(data["savings"]),
            savings_rate=float(data["savings_rate"]),
        )

    def resolve_investment_distribution(self, info):
        from .domain import classify_account_balance

        user = info.context.user
        if not user or not user.is_authenticated:
            return []

        accounts = Account.objects.filter(connection__user=user)
        distribution = {}

        for account in accounts:
            class_name, amount = classify_account_balance(account)
            label_map = {
                "cash": "Caixa",
                "investments": "Investimentos",
                "credit_cards": "Cartões",
            }
            label = label_map.get(class_name, class_name)
            value = float(abs(amount))
            distribution[label] = distribution.get(label, 0) + value

        total = sum(distribution.values())
        if total == 0:
            return []

        result = []
        for label, value in sorted(distribution.items(), key=lambda x: -x[1]):
            result.append(
                InvestmentDistributionItemType(
                    label=label,
                    value=value,
                    percentage=(value / total) * 100,
                )
            )
        return result

    def resolve_financial_freedom_projection(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return None

        summary = _request_cached(
            info, "financial_summary", lambda: build_user_financial_summary(user)
        )
        net_worth = float(summary["net_worth"])

        # Uma leitura por mes. Antes havia um laco para a media de poupanca e outro
        # para a de despesa, sobre os mesmos tres meses -- o dobro do custo. Os
        # meses tambem eram aproximados por `hoje - 30*i dias`, o que a partir de
        # 31/03 caia no proprio marco e pulava fevereiro.
        averages = build_recent_month_averages(user, months=3)
        avg_monthly_savings = float(averages["savings"])
        avg_monthly_expenses = float(averages["expenses"])

        # Target: 25x annual expenses (4% rule)
        target_net_worth = avg_monthly_expenses * 12 * 25
        estimated_passive_income = target_net_worth * 0.04
        financial_runway_months = (
            int(net_worth / avg_monthly_expenses) if avg_monthly_expenses > 0 else 999
        )

        if target_net_worth <= 0:
            return FinancialFreedomProjectionType(
                current_net_worth=net_worth,
                monthly_savings=avg_monthly_savings,
                average_monthly_expenses=avg_monthly_expenses,
                target_net_worth=target_net_worth,
                estimated_passive_income=estimated_passive_income,
                financial_runway_months=financial_runway_months,
                estimated_retire_date=None,
                months_to_freedom=0,
                target_reached=True,
                conservative_months=0,
                base_months=0,
                aggressive_months=0,
            )

        months_to_freedom = 0
        if avg_monthly_savings > 0 and net_worth < target_net_worth:
            # Simplified: assuming average 8% annual return
            monthly_return = 0.08 / 12
            # FV = PMT * ((1+r)^n - 1) / r + PV * (1+r)^n
            # Solving for n: n = log((FV*r + PMT) / (PMT + PV*r)) / log(1+r)
            numerator = target_net_worth * monthly_return + avg_monthly_savings
            denominator = avg_monthly_savings + net_worth * monthly_return
            if denominator > 0 and numerator > denominator:
                months_to_freedom = int(
                    math.log(numerator / denominator) / math.log(1 + monthly_return)
                )
                if months_to_freedom < 0:
                    months_to_freedom = 0

        # Different scenarios with different assumed returns
        scenarios = {"conservative": 0.04, "base": 0.08, "aggressive": 0.12}
        scenario_months = {}
        for name, rate in scenarios.items():
            monthly_r = rate / 12
            if avg_monthly_savings > 0 and net_worth < target_net_worth:
                denom = avg_monthly_savings + net_worth * monthly_r
                if denom > 0:
                    m = int(
                        math.log((target_net_worth * monthly_r + avg_monthly_savings) / denom)
                        / math.log(1 + monthly_r)
                    )
                    scenario_months[name] = max(0, m)
                else:
                    scenario_months[name] = 999
            else:
                scenario_months[name] = 0

        from datetime import date

        retire_date = (
            add_months(date.today(), months_to_freedom).isoformat()
            if months_to_freedom > 0
            else None
        )

        return FinancialFreedomProjectionType(
            current_net_worth=net_worth,
            monthly_savings=avg_monthly_savings,
            average_monthly_expenses=avg_monthly_expenses,
            target_net_worth=target_net_worth,
            estimated_passive_income=estimated_passive_income,
            financial_runway_months=financial_runway_months,
            estimated_retire_date=retire_date,
            months_to_freedom=months_to_freedom,
            target_reached=net_worth >= target_net_worth,
            conservative_months=scenario_months.get("conservative", 0),
            base_months=scenario_months.get("base", 0),
            aggressive_months=scenario_months.get("aggressive", 0),
        )

    def resolve_subscriptions(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return Subscription.objects.none()
        return Subscription.objects.filter(user=user).order_by("-created_at")

    def resolve_subscription_payments(self, info, subscription_id=None):
        user = info.context.user
        if not user or not user.is_authenticated:
            return SubscriptionPayment.objects.none()
        qs = SubscriptionPayment.objects.filter(subscription__user=user).order_by("-due_date")
        if subscription_id:
            qs = qs.filter(subscription_id=subscription_id)
        return qs

    def resolve_categorization_rules(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return CategorizationRule.objects.none()
        return CategorizationRule.objects.filter(user=user).order_by("priority", "-created_at")

    def resolve_pension_plans(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return PensionPlan.objects.none()
        return PensionPlan.objects.filter(user=user)

    def resolve_investment_positions(self, info, investment_id=None):
        user = info.context.user
        if not user or not user.is_authenticated:
            return InvestmentPosition.objects.none()
        # `InvestmentPositionType` expoe `investment`: sem o select_related, cada
        # posicao dispara uma query para o proprio investimento.
        qs = (
            InvestmentPosition.objects.filter(investment__connection__user=user)
            .select_related("investment")
            .order_by("-as_of_date")
        )
        if investment_id:
            qs = qs.filter(investment_id=investment_id)
        return qs

    def resolve_subscription_overview(self, info, upcoming_days=30):
        user = info.context.user
        if not user or not user.is_authenticated:
            return None

        data = build_subscription_overview(user, upcoming_days=upcoming_days)

        def to_items(rows):
            return [
                SubscriptionScheduleItemType(
                    name=row["name"],
                    category=row["category"],
                    due_date=row["due_date"].isoformat(),
                    amount=float(row["amount"]),
                    status=row["status"],
                )
                for row in rows
            ]

        return SubscriptionOverviewType(
            monthly_recurring_total=float(data["monthly_recurring_total"]),
            active_count=data["active_count"],
            paid_this_month=float(data["paid_this_month"]),
            pending_this_month=float(data["pending_this_month"]),
            overdue_total=float(data["overdue_total"]),
            overdue=to_items(data["overdue"]),
            upcoming=to_items(data["upcoming"]),
        )

    def resolve_alerts(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return []
        return [AlertType(**alert) for alert in build_user_alerts(user)]
