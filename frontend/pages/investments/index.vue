<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL, formatPercent } from '@/composables/useCurrency'
import { formatIsoDate } from '@/composables/useDateFormat'
import { useInvestmentPerformance, VERDICT_LABELS, type VerdictStatus, type WindowSummary } from '@/composables/useInvestmentPerformance'
import { usePortfolioRisk } from '@/composables/usePortfolioRisk'
import { INVESTMENT_CATEGORY_COLORS } from '@/composables/useChartPalette'
import type { BenchmarkWindow } from '@/composables/useMarketBenchmarks'
import DonutChart from '@/components/investments/DonutChart.vue'
import VerdictBadge from '@/components/investments/VerdictBadge.vue'

definePageMeta({
  middleware: 'auth',
})

const uiStore = useUiStore()
const blurClass = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const {
  investments,
  totalValue,
  totalProfit,
  categories,
  portfolioWindows,
  portfolioVerdictCounts,
  needsAttention,
  market,
} = useInvestmentPerformance()
const { issuerSegments, indexerSegments, currencySegments } = usePortfolioRisk()

const signClass = (value: number | null): string => {
  if (value === null || value === 0) return 'text-sepia-400'
  return value > 0 ? 'text-azul-600' : 'text-vermelho-600'
}

const WINDOWS: { key: BenchmarkWindow; label: string }[] = [
  { key: 'm1', label: '1 mês' },
  { key: 'm3', label: '3 meses' },
  { key: 'm12', label: '12 meses' },
]

// Media de uma janela so e mostrada quando cobre ao menos metade da
// categoria/carteira -- abaixo disso ela descreve meia duzia de ativos, nao o todo.
const MIN_COVERAGE_TO_SHOW = 50
const windowRate = (summary: WindowSummary) => (summary.coverage >= MIN_COVERAGE_TO_SHOW ? summary.rate : null)

const categorySegments = computed(() =>
  categories.value.map((category) => ({
    key: category.key,
    label: category.label,
    value: category.totalValue,
    color: INVESTMENT_CATEGORY_COLORS[category.key],
    to: `/investments/${category.key}`,
  })),
)

const toDonut = (segments: { key: string; label: string; value: number }[]) =>
  segments.map(({ key, label, value }) => ({ key, label, value }))

const profitBase = computed(() => totalValue.value - totalProfit.value)
const totalProfitRate = computed(() => (profitBase.value > 0 ? (totalProfit.value / profitBase.value) * 100 : null))

const VERDICT_ORDER: VerdictStatus[] = ['keep', 'watch', 'review', 'unknown']
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold">Investimentos</h1>
        <p class="mt-1 text-sepia-600">Quanto cada parte da carteira rende e se está valendo a pena frente ao CDI.</p>
      </div>
    </div>

    <div v-if="!investments?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:chart-line" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum investimento encontrado.</p>
      <p class="mt-1 text-sm text-sepia-400">Conecte uma instituição para ver seus investimentos.</p>
    </div>

    <template v-else>
      <!-- Numeros principais -->
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Patrimônio investido</p>
          <p :class="['mt-2 font-mono text-2xl font-bold text-sepia-900', blurClass]">{{ formatBRL(totalValue) }}</p>
          <p class="mt-1 text-xs text-sepia-500">{{ investments.length }} ativos em {{ categories.length }} categorias</p>
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Lucro acumulado</p>
          <p :class="['mt-2 font-mono text-2xl font-bold', signClass(totalProfit), blurClass]">
            {{ totalProfit > 0 ? '+' : '' }}{{ formatBRL(totalProfit) }}
          </p>
          <p class="mt-1 text-xs text-sepia-500">
            <template v-if="totalProfitRate !== null">{{ formatPercent(totalProfitRate, { signed: true }) }} sobre o aplicado conhecido</template>
            <template v-else>Instituição não informou o valor aplicado</template>
          </p>
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Carteira no último mês</p>
          <p :class="['mt-2 font-mono text-2xl font-bold', signClass(windowRate(portfolioWindows.m1))]">
            {{ formatPercent(windowRate(portfolioWindows.m1), { signed: true }) }}
          </p>
          <p class="mt-1 text-xs text-sepia-500">
            CDI no mesmo período: {{ formatPercent(market.cdi('m1'), { signed: true }) }}
          </p>
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Vale a pena manter?</p>
          <div class="mt-3 flex flex-wrap gap-2">
            <template v-for="status in VERDICT_ORDER" :key="status">
              <VerdictBadge v-if="portfolioVerdictCounts[status]" :status="status" :count="portfolioVerdictCounts[status]" />
            </template>
          </div>
          <p class="mt-2 text-xs text-sepia-500">Comparado ao CDI do mesmo período</p>
        </div>
      </div>

      <!-- Graficos de composicao -->
      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-1 text-base font-semibold text-sepia-900">Por tipo de ativo</h3>
          <p class="mb-4 text-xs text-sepia-400">Clique em uma categoria para ver o rendimento de cada ativo.</p>
          <DonutChart :segments="categorySegments" center-label="Total" :max-segments="8" />
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-1 text-base font-semibold text-sepia-900">Por indexador</h3>
          <p class="mb-4 text-xs text-sepia-400">Quanto da carteira depende de CDI, IPCA, prefixado ou renda variável.</p>
          <DonutChart :segments="toDonut(indexerSegments)" center-label="Total" />
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-1 text-base font-semibold text-sepia-900">Por emissor</h3>
          <p class="mb-4 text-xs text-sepia-400">Concentração em um mesmo banco/empresa — o risco que não aparece produto a produto.</p>
          <DonutChart :segments="toDonut(issuerSegments)" center-label="Total" />
        </div>
        <div v-if="currencySegments.length > 1" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-4 text-base font-semibold text-sepia-900">Por moeda</h3>
          <DonutChart :segments="toDonut(currencySegments)" center-label="Total" />
        </div>
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-1 text-base font-semibold text-sepia-900">Referências do mercado</h3>
          <p class="mb-4 text-xs text-sepia-400">A régua usada para dizer se um investimento vale a pena.</p>
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wide text-sepia-400">
                <th class="pb-2 font-medium">Índice</th>
                <th v-for="w in WINDOWS" :key="w.key" class="pb-2 text-right font-medium">{{ w.label }}</th>
              </tr>
            </thead>
            <tbody class="font-mono">
              <tr class="border-t border-sepia-100">
                <td class="py-2 font-sans text-sepia-700">CDI</td>
                <td v-for="w in WINDOWS" :key="w.key" class="py-2 text-right text-sepia-900">{{ formatPercent(market.cdi(w.key)) }}</td>
              </tr>
              <tr class="border-t border-sepia-100">
                <td class="py-2 font-sans text-sepia-700">IPCA (inflação)</td>
                <td v-for="w in WINDOWS" :key="w.key" class="py-2 text-right text-sepia-900">{{ formatPercent(market.ipca(w.key)) }}</td>
              </tr>
            </tbody>
          </table>
          <p class="mt-3 text-xs text-sepia-500">
            <template v-if="market.cdiAnnualRate.value !== null">CDI atual: {{ formatPercent(market.cdiAnnualRate.value) }} ao ano.</template>
            <template v-if="market.benchmarks.value?.cdi.as_of"> Atualizado em {{ formatIsoDate(market.benchmarks.value.cdi.as_of) }}.</template>
          </p>
        </div>
      </div>

      <!-- Categorias -->
      <div>
        <h2 class="mb-3 text-lg font-semibold text-sepia-900">Rendimento por categoria</h2>
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <NuxtLink
            v-for="category in categories"
            :key="category.key"
            :to="`/investments/${category.key}`"
            class="group rounded-lg border border-sepia-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-2">
                <span class="h-3 w-3 shrink-0 rounded-full" :style="{ backgroundColor: INVESTMENT_CATEGORY_COLORS[category.key] }" />
                <p class="font-semibold text-sepia-900">{{ category.label }}</p>
                <span
                  v-if="category.estimated"
                  class="rounded-full bg-sepia-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sepia-500"
                  title="Categoria estimada pelo código do ativo"
                >estimado</span>
              </div>
              <Icon icon="mdi:chevron-right" class="h-5 w-5 shrink-0 text-sepia-400 group-hover:text-sepia-700" />
            </div>
            <div class="mt-3 flex items-baseline justify-between gap-2">
              <p :class="['font-mono text-xl font-bold text-sepia-900', blurClass]">{{ formatBRL(category.totalValue) }}</p>
              <p class="font-mono text-sm text-sepia-500">{{ formatPercent(category.share) }} da carteira</p>
            </div>
            <p :class="['font-mono text-xs', signClass(category.totalProfit), blurClass]">
              {{ category.totalProfit > 0 ? '+' : '' }}{{ formatBRL(category.totalProfit) }} de lucro
            </p>

            <dl class="mt-4 grid grid-cols-3 gap-2 border-t border-sepia-100 pt-3 text-center">
              <div v-for="w in WINDOWS" :key="w.key">
                <dt class="text-[11px] text-sepia-400">{{ w.label }}</dt>
                <dd :class="['font-mono text-sm font-semibold', signClass(windowRate(category.windows[w.key]))]">
                  {{ formatPercent(windowRate(category.windows[w.key]), { signed: true }) }}
                </dd>
                <dd class="font-mono text-[10px] text-sepia-400">CDI {{ formatPercent(market.cdi(w.key)) }}</dd>
              </div>
            </dl>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <template v-for="status in VERDICT_ORDER" :key="status">
                <VerdictBadge v-if="category.verdictCounts[status]" :status="status" :count="category.verdictCounts[status]" size="sm" />
              </template>
            </div>
          </NuxtLink>
        </div>
      </div>

      <!-- O que reavaliar -->
      <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">O que merece sua atenção</h3>
        <p class="mb-4 text-xs text-sepia-400">
          Ativos que renderam abaixo do CDI no período mais longo disponível. Não é recomendação de venda — é o
          ponto de partida para revisar se o motivo de ter esse ativo ainda vale.
        </p>
        <p v-if="!needsAttention.length" class="text-sm text-sepia-500">
          Nenhum ativo com histórico suficiente está rendendo abaixo do CDI.
        </p>
        <ul v-else class="divide-y divide-sepia-100">
          <li v-for="row in needsAttention" :key="row.investment.id" class="flex flex-wrap items-start justify-between gap-3 py-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <NuxtLink :to="`/investments/${row.investment.display_category}`" class="font-medium !text-sepia-900 hover:underline">
                  {{ row.investment.name }}
                </NuxtLink>
                <span class="text-xs text-sepia-400">{{ row.investment.display_category_label }}</span>
              </div>
              <p class="mt-0.5 text-xs text-sepia-500">{{ row.verdict.reason }}</p>
            </div>
            <div class="flex items-center gap-3">
              <span :class="['font-mono text-sm text-sepia-900', blurClass]">{{ formatBRL(row.marketValue) }}</span>
              <VerdictBadge :status="row.verdict.status" />
            </div>
          </li>
        </ul>
      </div>

      <p class="text-xs text-sepia-400">
        Veredito: <strong>{{ VERDICT_LABELS.keep }}</strong> rende ao menos o CDI; <strong>{{ VERDICT_LABELS.watch }}</strong>
        entre 80% e 100% do CDI (pode compensar se for isento de IR); <strong>{{ VERDICT_LABELS.review }}</strong> abaixo de 80% do
        CDI ou negativo. Usa a janela mais longa disponível (12 meses, desde a compra ou 3 meses). Rendimentos que a
        instituição não informa são estimados pelo histórico de posições sincronizadas.
      </p>
    </template>
  </section>
</template>
