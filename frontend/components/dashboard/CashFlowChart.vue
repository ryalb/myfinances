<script setup lang="ts">
import { formatBRL } from '@/composables/useCurrency'

const props = defineProps<{
  data: { year: number; month: number; income: number; expenses: number; savings: number; savings_rate: number }[]
}>()

const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

const chartData = computed(() => {
  // Escala comum às duas séries: uma escala por série faria barras de valores
  // diferentes terminarem na mesma altura.
  const maxVal = Math.max(...props.data.flatMap((d) => [d.income, d.expenses]), 1)

  return props.data.map((d) => ({
    month: `${months[d.month - 1]}/${String(d.year).slice(2)}`,
    // Percentual da área de plotagem. Receita e despesa ficam lado a lado, cada uma
    // partindo da mesma linha de base: antes estavam empilhadas, e como cada uma
    // podia chegar a 100% da altura do contêiner, juntas estouravam o dobro dele.
    incomeHeight: (d.income / maxVal) * 100,
    expensesHeight: (d.expenses / maxVal) * 100,
    savingsRate: d.savings_rate,
    rawIncome: d.income,
    rawExpenses: d.expenses,
    rawSavings: d.savings,
  }))
})
</script>

<template>
  <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
    <div class="mb-1 flex flex-wrap items-baseline justify-between gap-2">
      <h3 class="text-lg font-semibold text-sepia-900">Fluxo de Caixa — Últimos 12 Meses</h3>
      <div class="flex gap-4 text-xs">
        <span class="flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-emerald-500" />
          Receitas
        </span>
        <span class="flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-rose-500" />
          Despesas
        </span>
      </div>
    </div>
    <p class="mb-4 text-xs text-sepia-400">O percentual acima de cada mês é a taxa de poupança.</p>

    <div class="flex items-stretch gap-2" style="height: 240px">
      <div
        v-for="(item, idx) in chartData"
        :key="idx"
        class="flex min-w-0 flex-1 flex-col items-center gap-1"
      >
        <span class="text-[11px] leading-none text-sepia-500">{{ item.savingsRate.toFixed(0) }}%</span>

        <!-- Área de plotagem: as duas barras crescem da mesma linha de base -->
        <div class="flex w-full flex-1 items-end justify-center gap-0.5">
          <div
            class="w-1/2 rounded-t-sm bg-emerald-500 transition-all"
            :style="{ height: `${item.incomeHeight}%` }"
            :title="`${item.month} · Receita: ${formatBRL(item.rawIncome)}`"
          />
          <div
            class="w-1/2 rounded-t-sm bg-rose-500 transition-all"
            :style="{ height: `${item.expensesHeight}%` }"
            :title="`${item.month} · Despesa: ${formatBRL(item.rawExpenses)}`"
          />
        </div>

        <span class="truncate text-[11px] leading-none text-sepia-400">{{ item.month }}</span>
      </div>
    </div>
  </div>
</template>
