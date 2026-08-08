import math

import graphene
from django.utils import timezone
from graphene_django import DjangoObjectType

from .consolidation import build_monthly_cash_flow, build_user_financial_summary
from .models import (
    Account,
    CategorizationRule,
    FinancialInstitution,
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


class AccountType(DjangoObjectType):
    class Meta:
        model = Account
        fields = ("id", "name", "type", "currency", "balance", "available_balance")


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
    class Meta:
        model = PensionPlan
        fields = ("id", "name", "provider", "balance")


class InvestmentPositionType(DjangoObjectType):
    class Meta:
        model = InvestmentPosition
        fields = ("id", "investment", "as_of_date", "quantity", "unit_price", "market_value")


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

    def resolve_institutions(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return FinancialInstitution.objects.none()
        return FinancialInstitution.objects.all().order_by("name")

    def resolve_accounts(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return Account.objects.none()
        return Account.objects.filter(connection__user=user).order_by("name")

    def resolve_net_worth_history(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return NetWorthSnapshot.objects.none()
        return NetWorthSnapshot.objects.filter(user=user).order_by("-date")

    def resolve_financial_summary(self, info):
        user = info.context.user
        if not user or not user.is_authenticated:
            return None
        data = build_user_financial_summary(user)
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
        from datetime import timedelta

        user = info.context.user
        if not user or not user.is_authenticated:
            return None

        summary = build_user_financial_summary(user)
        net_worth = float(summary["net_worth"])

        # Calculate average monthly savings from last 3 months
        now = timezone.localdate()
        flows = []
        for i in range(1, 4):
            d = now - timedelta(days=30 * i)
            flow = build_monthly_cash_flow(user, year=d.year, month=d.month)
            flows.append(float(flow["savings"]))

        avg_monthly_savings = sum(flows) / len(flows) if flows else 0

        # Target: 25x annual expenses (4% rule)
        avg_monthly_expenses = (
            sum(
                float(build_monthly_cash_flow(user, year=d.year, month=d.month)["expenses"])
                for d in [now - timedelta(days=30 * i) for i in range(1, 4)]
            )
            / 3
        )
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
            (date.today() + timedelta(days=months_to_freedom * 30)).isoformat()
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
        return PensionPlan.objects.filter(connection__user=user)

    def resolve_investment_positions(self, info, investment_id=None):
        user = info.context.user
        if not user or not user.is_authenticated:
            return InvestmentPosition.objects.none()
        qs = InvestmentPosition.objects.filter(investment__connection__user=user).order_by(
            "-as_of_date"
        )
        if investment_id:
            qs = qs.filter(investment_id=investment_id)
        return qs
