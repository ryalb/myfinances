<script setup lang="ts">
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const metrics = await useDashboardMetrics()
const { history: cashFlow } = useCashFlowHistory()
const { history: netWorthHistory } = useNetWorthHistory()

// Fetch financial freedom projection via GraphQL
const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}`, 'Content-Type': 'application/json' } : {}

const { data: freedomData } = await useFetch<{ data: { financialFreedomProjection: Record<string, unknown> } }>(
  `${config.public.graphqlEndpoint}`,
  {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/json' },
  body: {
    query: `{ financialFreedomProjection { currentNetWorth monthlySavings averageMonthlyExpenses targetNetWorth estimatedPassiveIncome financialRunwayMonths estimatedRetireDate monthsToFreedom targetReached conservativeMonths baseMonths aggressiveMonths } }`,
  },
    key: 'dashboard-freedom',
    immediate: false,
  },
)

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

    <!-- Charts row 1: Net worth evolution + Cash flow -->
    <div class="grid gap-4 lg:grid-cols-2">
      <dashboard-net-worth-chart v-if="netWorthHistory?.length" :data="netWorthHistory" />
      <div v-else class="rounded-xl border border-sepia-200 bg-white p-8 text-center shadow-sm">
        <p class="text-sepia-400">Sem dados históricos suficientes.</p>
      </div>

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
      <dashboard-financial-freedom-card
        v-if="freedomData?.data?.financialFreedomProjection"
        :current-net-worth="(freedomData.data.financialFreedomProjection.currentNetWorth as number) || 0"
        :monthly-savings="(freedomData.data.financialFreedomProjection.monthlySavings as number) || 0"
        :average-monthly-expenses="(freedomData.data.financialFreedomProjection.averageMonthlyExpenses as number) || 0"
        :target-net-worth="(freedomData.data.financialFreedomProjection.targetNetWorth as number) || 0"
        :estimated-passive-income="(freedomData.data.financialFreedomProjection.estimatedPassiveIncome as number) || 0"
        :financial-runway-months="(freedomData.data.financialFreedomProjection.financialRunwayMonths as number) || 0"
        :estimated-retire-date="(freedomData.data.financialFreedomProjection.estimatedRetireDate as string) || null"
        :months-to-freedom="(freedomData.data.financialFreedomProjection.monthsToFreedom as number) || 0"
        :target-reached="(freedomData.data.financialFreedomProjection.targetReached as boolean) || false"
        :conservative-months="(freedomData.data.financialFreedomProjection.conservativeMonths as number) || 0"
        :base-months="(freedomData.data.financialFreedomProjection.baseMonths as number) || 0"
        :aggressive-months="(freedomData.data.financialFreedomProjection.aggressiveMonths as number) || 0"
      />
      <div v-else class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-4 text-lg font-semibold text-sepia-900">Liberdade Financeira</h3>
        <p class="py-8 text-center text-sm text-sepia-400">Calcule suas projeções conectando instituições e sincronizando dados.</p>
      </div>
    </div>
  </section>
</template>
