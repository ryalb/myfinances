<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL, formatPercent } from '@/composables/useCurrency'
import { formatIsoDate } from '@/composables/useDateFormat'
import {
  PRICE_ONLY_CATEGORIES,
  useInvestmentPerformance,
  VERDICT_LABELS,
  type PerformanceRow,
  type VerdictStatus,
} from '@/composables/useInvestmentPerformance'
import { CHART_PALETTE, INVESTMENT_CATEGORY_COLORS } from '@/composables/useChartPalette'
import type { BenchmarkWindow } from '@/composables/useMarketBenchmarks'
import DonutChart from '@/components/investments/DonutChart.vue'
import VerdictBadge from '@/components/investments/VerdictBadge.vue'

definePageMeta({
  middleware: 'auth',
})

const route = useRoute()
const categoryKey = computed(() => String(route.params.category))

const uiStore = useUiStore()
const blurClass = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const { categories, market, investments } = useInvestmentPerformance()
const category = computed(() => categories.value.find((c) => c.key === categoryKey.value) || null)

const signClass = (value: number | null): string => {
  if (value === null || value === 0) return 'text-sepia-400'
  return value > 0 ? 'text-azul-600' : 'text-vermelho-600'
}

const WINDOWS: { key: BenchmarkWindow; label: string }[] = [
  { key: 'm1', label: 'Último mês' },
  { key: 'm3', label: 'Últimos 3 meses' },
  { key: 'm12', label: 'Últimos 12 meses' },
]
const isPriceOnly = computed(() => PRICE_ONLY_CATEGORIES.has(categoryKey.value))

const assetSegments = computed(() =>
  (category.value?.rows || []).map((row, index) => ({
    key: String(row.investment.id),
    label: row.investment.code || row.investment.name,
    value: row.marketValue,
    color: CHART_PALETTE[index % CHART_PALETTE.length],
  })),
)

const verdictSegments = computed(() => {
  const rows = category.value?.rows || []
  const colors: Record<VerdictStatus, string> = { keep: '#2e6c99', watch: '#eda100', review: '#a5423a', unknown: '#cfb683' }
  return (Object.keys(colors) as VerdictStatus[]).map((status) => ({
    key: status,
    label: VERDICT_LABELS[status],
    value: rows.filter((r) => r.verdict.status === status).reduce((sum, r) => sum + r.marketValue, 0),
    color: colors[status],
  }))
})

const secondaryInfo = (row: PerformanceRow) => {
  const parts: string[] = []
  const investment = row.investment
  if (investment.code && investment.code !== investment.name) parts.push(investment.code)
  if (investment.issuer) parts.push(investment.issuer)
  if (investment.indexer_additional_info) parts.push(investment.indexer_additional_info)
  if (investment.due_date) parts.push(`vence ${formatIsoDate(investment.due_date)}`)
  if (investment.tax_exempt) parts.push('isento de IR')
  return parts.join(' · ')
}

const sincePurchaseLabel = (row: PerformanceRow) => {
  if (row.sincePurchaseRate === null) return '—'
  return formatPercent(row.sincePurchaseRate, { signed: true })
}
</script>

<template>
  <section class="space-y-6">
    <NuxtLink to="/investments" class="inline-flex items-center gap-1 text-sm">
      <Icon icon="mdi:arrow-left" class="h-4 w-4" />
      Investimentos
    </NuxtLink>

    <div v-if="!investments?.length || !category" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:chart-donut" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum investimento nesta categoria.</p>
    </div>

    <template v-else>
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="flex items-center gap-2 text-2xl font-semibold">
            <span class="h-3.5 w-3.5 rounded-full" :style="{ backgroundColor: INVESTMENT_CATEGORY_COLORS[category.key] }" />
            {{ category.label }}
          </h1>
          <p class="mt-1 text-sepia-600">
            {{ category.rows.length }} {{ category.rows.length === 1 ? 'ativo' : 'ativos' }} ·
            {{ formatPercent(category.share) }} da carteira
          </p>
        </div>
        <div class="text-right">
          <p :class="['font-mono text-2xl font-bold text-sepia-900', blurClass]">{{ formatBRL(category.totalValue) }}</p>
          <p :class="['font-mono text-sm font-medium', signClass(category.totalProfit), blurClass]">
            {{ category.totalProfit > 0 ? '+' : '' }}{{ formatBRL(category.totalProfit) }} de lucro
          </p>
        </div>
      </div>

      <!-- Rendimento medio da categoria x CDI -->
      <div class="grid gap-4 sm:grid-cols-3">
        <div v-for="w in WINDOWS" :key="w.key" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">{{ w.label }}</p>
          <p :class="['mt-2 font-mono text-2xl font-bold', signClass(category.windows[w.key].rate)]">
            {{ formatPercent(category.windows[w.key].rate, { signed: true }) }}
          </p>
          <p class="mt-1 text-xs text-sepia-500">
            CDI: {{ formatPercent(market.cdi(w.key), { signed: true }) }} · IPCA: {{ formatPercent(market.ipca(w.key), { signed: true }) }}
          </p>
          <p v-if="category.windows[w.key].rate !== null && category.windows[w.key].coverage < 99.5" class="mt-1 text-[11px] text-sepia-400">
            Média de {{ formatPercent(category.windows[w.key].coverage) }} do valor — os demais ativos ainda não têm histórico.
          </p>
          <p v-else-if="category.windows[w.key].rate === null" class="mt-1 text-[11px] text-sepia-400">
            Histórico de posições ainda não cobre esse período.
          </p>
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-4 text-base font-semibold text-sepia-900">Distribuição entre os ativos</h3>
          <DonutChart :segments="assetSegments" :center-label="category.label" />
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-1 text-base font-semibold text-sepia-900">Vale a pena manter?</h3>
          <p class="mb-4 text-xs text-sepia-400">Quanto do valor da categoria está em cada veredito.</p>
          <DonutChart :segments="verdictSegments" center-label="Total" />
        </div>
      </div>

      <div
        v-if="isPriceOnly"
        class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
      >
        <Icon icon="mdi:information-outline" class="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          O rendimento aqui é só a variação de preço da cota/ação. Dividendos e rendimentos já pagos caem na sua conta e
          não entram nessa conta — o retorno real costuma ser maior, principalmente em FIIs.
        </p>
      </div>

      <!-- Tabela por ativo -->
      <div class="rounded-lg border border-sepia-200 bg-white shadow-sm">
        <table class="hidden w-full text-sm lg:table">
          <thead>
            <tr class="border-b border-sepia-200 text-left text-xs font-medium uppercase tracking-wide text-sepia-400">
              <th class="px-4 py-3">Ativo</th>
              <th class="px-4 py-3 text-right">Valor atual</th>
              <th class="px-4 py-3 text-right">1 mês</th>
              <th class="px-4 py-3 text-right">3 meses</th>
              <th class="px-4 py-3 text-right">12 meses</th>
              <th class="px-4 py-3 text-right">Desde a compra</th>
              <th class="px-4 py-3">Vale a pena?</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in category.rows" :key="row.investment.id" class="border-b border-sepia-100 align-top last:border-0">
              <td class="px-4 py-3">
                <p class="font-medium text-sepia-900">{{ row.investment.name }}</p>
                <p v-if="secondaryInfo(row)" class="mt-0.5 text-xs text-sepia-400">{{ secondaryInfo(row) }}</p>
              </td>
              <td class="px-4 py-3 text-right">
                <p :class="['font-mono font-semibold text-sepia-900', blurClass]">{{ formatBRL(row.marketValue) }}</p>
                <p v-if="row.amountProfit !== null" :class="['font-mono text-xs', signClass(row.amountProfit), blurClass]">
                  {{ row.amountProfit > 0 ? '+' : '' }}{{ formatBRL(row.amountProfit) }}
                </p>
              </td>
              <td :class="['px-4 py-3 text-right font-mono', signClass(row.lastMonthRate)]">
                {{ formatPercent(row.lastMonthRate, { signed: true }) }}
              </td>
              <td :class="['px-4 py-3 text-right font-mono', signClass(row.threeMonthRate)]">
                {{ formatPercent(row.threeMonthRate, { signed: true }) }}
              </td>
              <td :class="['px-4 py-3 text-right font-mono', signClass(row.lastTwelveMonthsRate)]">
                {{ formatPercent(row.lastTwelveMonthsRate, { signed: true }) }}
              </td>
              <td class="px-4 py-3 text-right font-mono">
                <p :class="signClass(row.sincePurchaseRate)">{{ sincePurchaseLabel(row) }}</p>
                <p v-if="row.sincePurchaseAnnualRate !== null" class="text-[11px] text-sepia-400">
                  {{ formatPercent(row.sincePurchaseAnnualRate, { signed: true }) }} a.a.
                </p>
                <p v-if="row.purchaseDate" class="text-[11px] text-sepia-400">{{ formatIsoDate(row.purchaseDate) }}</p>
              </td>
              <td class="max-w-xs px-4 py-3">
                <VerdictBadge :status="row.verdict.status" />
                <p class="mt-1 text-xs text-sepia-500">{{ row.verdict.reason }}</p>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Lista empilhada: abaixo de lg -->
        <div class="block divide-y divide-sepia-100 lg:hidden">
          <div v-for="row in category.rows" :key="row.investment.id" class="px-4 py-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="font-medium text-sepia-900">{{ row.investment.name }}</p>
                <p v-if="secondaryInfo(row)" class="mt-0.5 text-xs text-sepia-400">{{ secondaryInfo(row) }}</p>
              </div>
              <p :class="['text-right font-mono font-semibold text-sepia-900', blurClass]">{{ formatBRL(row.marketValue) }}</p>
            </div>
            <div class="mt-2 grid grid-cols-4 gap-2 text-center text-xs">
              <div>
                <p class="text-sepia-400">1m</p>
                <p :class="['font-mono', signClass(row.lastMonthRate)]">{{ formatPercent(row.lastMonthRate, { signed: true }) }}</p>
              </div>
              <div>
                <p class="text-sepia-400">3m</p>
                <p :class="['font-mono', signClass(row.threeMonthRate)]">{{ formatPercent(row.threeMonthRate, { signed: true }) }}</p>
              </div>
              <div>
                <p class="text-sepia-400">12m</p>
                <p :class="['font-mono', signClass(row.lastTwelveMonthsRate)]">{{ formatPercent(row.lastTwelveMonthsRate, { signed: true }) }}</p>
              </div>
              <div>
                <p class="text-sepia-400">Compra</p>
                <p :class="['font-mono', signClass(row.sincePurchaseRate)]">{{ sincePurchaseLabel(row) }}</p>
              </div>
            </div>
            <div class="mt-2">
              <VerdictBadge :status="row.verdict.status" />
              <p class="mt-1 text-xs text-sepia-500">{{ row.verdict.reason }}</p>
            </div>
          </div>
        </div>
      </div>

      <p class="text-xs text-sepia-400">
        "Vale a pena?" compara o rendimento com o CDI do mesmo período, na janela mais longa disponível (12 meses,
        desde a compra ou 3 meses). Com menos de 3 meses de histórico não há veredito. Rendimentos não informados pela
        instituição são estimados pelo histórico de posições sincronizadas, só quando a quantidade não mudou (aporte ou
        resgate distorceriam a conta).
      </p>
    </template>
  </section>
</template>
