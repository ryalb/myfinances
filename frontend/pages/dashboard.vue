<script setup lang="ts">
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const metrics = await useDashboardMetrics()
const { history: cashFlow } = useCashFlowHistory()
const { history: netWorthHistory } = useNetWorthHistory()
const { projection: freedom } = useFinancialFreedom()
const { overview: subscriptions } = useSubscriptionOverview()

const summaryCards = [
  {
    label: 'Patrimônio total',
    value: formatBRL(metrics.patrimonyTotal),
    sublabel: 'Ativos totais',
    icon: 'mdi:wallet',
    color: 'emerald',
  },
  {
    label: 'Patrimônio líquido',
    value: formatBRL(metrics.netBalance),
    sublabel: `Ativos: ${formatBRL(metrics.assets)} · Passivos: ${formatBRL(metrics.liabilities)}`,
    icon: 'mdi:chart-histogram',
    color: 'blue',
  },
  {
    label: 'Receitas mensais',
    value: formatBRL(metrics.monthlyIncome),
    sublabel: `Despesas: ${formatBRL(metrics.monthlyExpenses)}`,
    icon: 'mdi:arrow-up-bold',
    color: 'emerald',
  },
  {
    label: 'Taxa de poupança',
    value: `${metrics.savingsRate.toFixed(1)}%`,
    sublabel: `Poupança: ${formatBRL(Math.max(0, metrics.monthlyIncome - metrics.monthlyExpenses))}`,
    icon: 'mdi:piggy-bank',
    color: metrics.savingsRate >= 20 ? 'emerald' : metrics.savingsRate >= 10 ? 'amber' : 'rose',
  },
]
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Dashboard</h1>

    <!-- Summary cards -->
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <dashboard-metric-card v-for="card in summaryCards" :key="card.label" v-bind="card" />
    </div>

    <!-- Evolução patrimonial: linha própria, 30 pontos precisam de largura -->
    <div class="grid gap-4">
      <dashboard-net-worth-chart v-if="netWorthHistory?.length" :data="netWorthHistory" />
      <div v-else class="rounded-xl border border-sepia-200 bg-white p-8 text-center shadow-sm">
        <p class="text-sepia-400">Sem dados históricos suficientes.</p>
      </div>
    </div>

    <!-- Fluxo de caixa: 12 meses × 2 séries não caem em meia largura -->
    <div class="grid gap-4">
      <dashboard-cash-flow-chart v-if="cashFlow?.length" :data="cashFlow" />
      <div v-else class="rounded-xl border border-sepia-200 bg-white p-8 text-center shadow-sm">
        <p class="text-sepia-400">Carregando fluxo de caixa...</p>
      </div>
    </div>

    <!-- Charts row 2: Asset distribution + Liabilities -->
    <div class="grid gap-4 lg:grid-cols-2">
      <dashboard-asset-distribution :breakdown="metrics.breakdown" />
      <dashboard-liabilities-breakdown
        :total-liabilities="metrics.liabilities"
        :credit-cards="metrics.breakdown.creditCards"
        :other-debts="metrics.breakdown.debts"
      />
    </div>

    <!-- Charts row 3: Financial freedom -->
    <div class="grid gap-4 lg:grid-cols-1">
      <dashboard-financial-freedom-card v-if="freedom" v-bind="freedom" />
      <div v-else class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-sepia-900">Liberdade Financeira</h3>
        <p class="py-8 text-center text-sm text-sepia-400">Calcule suas projeções conectando instituições e sincronizando dados.</p>
      </div>
    </div>

    <!-- Charts row 4: Subscriptions and recurring commitments -->
    <div class="grid gap-4 lg:grid-cols-1">
      <dashboard-subscriptions-overview v-if="subscriptions" :overview="subscriptions" />
      <div v-else class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-sepia-900">Assinaturas e Recorrentes</h3>
        <p class="py-8 text-center text-sm text-sepia-400">Cadastre suas despesas fixas para acompanhar vencimentos e pagamentos.</p>
      </div>
    </div>
  </section>
</template>
