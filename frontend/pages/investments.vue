<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL, formatPercent } from '@/composables/useCurrency'
import { formatIsoDate } from '@/composables/useDateFormat'
import { useInvestments } from '@/composables/useInvestments'
import { usePortfolioRisk } from '@/composables/usePortfolioRisk'
import CompositionBar from '@/components/investments/CompositionBar.vue'

definePageMeta({
  middleware: 'auth',
})

const uiStore = useUiStore()
const blurClass = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const { investments, groups, totalValue, totalProfit, compositionSegments } = useInvestments()
const { issuerSegments, indexerSegments, currencySegments } = usePortfolioRisk()

const signClass = (value: number | null): string => {
  if (value === null || value === 0) return 'text-sepia-400'
  return value > 0 ? 'text-azul-600' : 'text-vermelho-600'
}

const totalProfitClass = computed(() => signClass(totalProfit.value))

const secondaryInfo = (investment: { code: string; issuer: string; due_date: string | null }) => {
  const parts = []
  if (investment.code) parts.push(investment.code)
  if (investment.issuer) parts.push(investment.issuer)
  if (investment.due_date) parts.push(`vence ${formatIsoDate(investment.due_date)}`)
  return parts.join(' · ')
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold">Investimentos</h1>
        <p class="mt-1 text-sepia-600">Sua carteira sincronizada via Open Finance, por categoria.</p>
      </div>
      <div v-if="investments?.length" class="text-right">
        <p :class="['font-mono text-2xl font-bold text-sepia-900', blurClass]">{{ formatBRL(totalValue) }}</p>
        <p :class="['font-mono text-sm font-medium', totalProfitClass, blurClass]">
          {{ totalProfit > 0 ? '+' : '' }}{{ formatBRL(totalProfit) }} de lucro
        </p>
      </div>
    </div>

    <div v-if="!investments?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:chart-line" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum investimento encontrado.</p>
      <p class="mt-1 text-sm text-sepia-400">Conecte uma instituição para ver seus investimentos.</p>
    </div>

    <template v-else>
      <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-4 text-base font-semibold text-sepia-900">Composição da carteira</h3>
        <CompositionBar :segments="compositionSegments" />
      </div>

      <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">Diagnóstico de concentração</h3>
        <p class="mb-4 text-xs text-sepia-400">
          Riscos que não aparecem olhando produto por produto: quanto a carteira depende do mesmo
          emissor, do mesmo indexador ou de uma única moeda.
        </p>
        <div class="space-y-5">
          <div>
            <h4 class="mb-2 text-sm font-medium text-sepia-700">Por emissor</h4>
            <CompositionBar :segments="issuerSegments" />
          </div>
          <div>
            <h4 class="mb-2 text-sm font-medium text-sepia-700">Por indexador</h4>
            <CompositionBar :segments="indexerSegments" />
          </div>
          <div>
            <h4 class="mb-2 text-sm font-medium text-sepia-700">Por moeda</h4>
            <CompositionBar :segments="currencySegments" />
          </div>
        </div>
      </div>

      <NuxtLink
        to="/portfolio-builder"
        class="flex items-center justify-between gap-3 rounded-lg border border-sepia-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
      >
        <div class="flex items-center gap-3">
          <Icon icon="mdi:target-arrow" class="h-6 w-6 shrink-0 text-sepia-700" />
          <div>
            <p class="font-semibold text-sepia-900">Construtor de portfólio</p>
            <p class="text-sm text-sepia-500">Defina metas de alocação e veja o desvio entre alvo e carteira real.</p>
          </div>
        </div>
        <Icon icon="mdi:chevron-right" class="h-5 w-5 shrink-0 text-sepia-400" />
      </NuxtLink>

      <div class="rounded-lg border border-sepia-200 bg-white shadow-sm">
        <!-- Tabela: md e acima -->
        <table class="hidden w-full text-sm md:table">
          <thead>
            <tr class="border-b border-sepia-200 text-left text-xs font-medium uppercase tracking-wide text-sepia-400">
              <th class="px-4 py-3">Ativo</th>
              <th class="px-4 py-3 text-right">Valor atual</th>
              <th class="px-4 py-3 text-right">Rend. mês</th>
              <th class="px-4 py-3 text-right">Rend. 12m</th>
              <th class="px-4 py-3 text-right">Lucro</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in groups" :key="group.key">
              <tr class="bg-sepia-50">
                <td colspan="5" class="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-sepia-500">
                  {{ group.label }}
                  <span
                    v-if="group.estimated"
                    class="ml-1 rounded-full bg-sepia-100 px-1.5 py-0.5 text-[10px] font-medium normal-case tracking-normal text-sepia-500"
                    title="Categoria estimada pelo código do ativo"
                  >
                    estimado
                  </span>
                </td>
              </tr>
              <tr v-for="row in group.rows" :key="row.investment.id" class="border-b border-sepia-100">
                <td class="px-4 py-3">
                  <p class="font-medium text-sepia-900">{{ row.investment.name }}</p>
                  <p v-if="secondaryInfo(row.investment)" class="mt-0.5 text-xs text-sepia-400">
                    {{ secondaryInfo(row.investment) }}
                    <span v-if="row.investment.tax_exempt" class="ml-1 text-sepia-400">· isento de IR</span>
                  </p>
                </td>
                <td :class="['px-4 py-3 text-right font-mono font-semibold text-sepia-900', blurClass]">
                  {{ formatBRL(row.marketValue) }}
                </td>
                <td :class="['px-4 py-3 text-right font-mono', signClass(row.lastMonthRate)]">
                  {{ formatPercent(row.lastMonthRate, { signed: true }) }}
                </td>
                <td :class="['px-4 py-3 text-right font-mono', signClass(row.lastTwelveMonthsRate)]">
                  {{ formatPercent(row.lastTwelveMonthsRate, { signed: true }) }}
                </td>
                <td :class="['px-4 py-3 text-right font-mono', signClass(row.amountProfit), blurClass]">
                  {{ row.amountProfit === null ? '—' : formatBRL(row.amountProfit) }}
                </td>
              </tr>
              <tr>
                <td class="ledger-total-rule px-4 py-2 text-xs font-medium text-sepia-500">
                  Subtotal · {{ group.rows.length }} {{ group.rows.length === 1 ? 'ativo' : 'ativos' }}
                </td>
                <td :class="['ledger-total-rule px-4 py-2 text-right font-mono text-sm font-semibold text-sepia-900', blurClass]">
                  {{ formatBRL(group.totalValue) }}
                </td>
                <td class="ledger-total-rule px-4 py-2" />
                <td class="ledger-total-rule px-4 py-2" />
                <td :class="['ledger-total-rule px-4 py-2 text-right font-mono text-sm font-semibold', signClass(group.totalProfit), blurClass]">
                  {{ formatBRL(group.totalProfit) }}
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <!-- Lista empilhada: abaixo de md -->
        <div class="block md:hidden">
          <div v-for="group in groups" :key="group.key">
            <p class="border-b border-sepia-200 bg-sepia-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-sepia-500">
              {{ group.label }}
              <span v-if="group.estimated" class="ml-1 normal-case tracking-normal text-sepia-400">(estimado)</span>
            </p>
            <div v-for="row in group.rows" :key="row.investment.id" class="border-b border-sepia-100 px-4 py-3">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="font-medium text-sepia-900">{{ row.investment.name }}</p>
                  <p v-if="secondaryInfo(row.investment)" class="mt-0.5 text-xs text-sepia-400">
                    {{ secondaryInfo(row.investment) }}
                  </p>
                </div>
                <p :class="['text-right font-mono font-semibold text-sepia-900', blurClass]">
                  {{ formatBRL(row.marketValue) }}
                </p>
              </div>
              <div class="mt-2 flex items-center gap-3 text-xs">
                <span :class="signClass(row.lastMonthRate)">mês {{ formatPercent(row.lastMonthRate, { signed: true }) }}</span>
                <span :class="signClass(row.lastTwelveMonthsRate)">12m {{ formatPercent(row.lastTwelveMonthsRate, { signed: true }) }}</span>
                <span v-if="row.amountProfit !== null" :class="['ml-auto font-mono', signClass(row.amountProfit), blurClass]">
                  {{ formatBRL(row.amountProfit) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
