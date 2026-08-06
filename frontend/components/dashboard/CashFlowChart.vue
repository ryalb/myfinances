<script setup lang="ts">
const props = defineProps<{
  data: { year: number; month: number; income: number; expenses: number; savings: number; savings_rate: number }[]
}>()

const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

const chartData = computed(() => {
  const maxVal = Math.max(...props.data.flatMap((d) => [d.income, d.expenses]), 1)

  return props.data.map((d) => ({
    month: `${months[d.month - 1]}/${d.year.toString().slice(2)}`,
    income: (d.income / maxVal) * 100,
    expenses: (d.expenses / maxVal) * 100,
    savings: d.savings >= 0 ? (d.savings / maxVal) * 100 : 0,
    savingsRate: d.savings_rate,
    rawIncome: d.income,
    rawExpenses: d.expenses,
    rawSavings: d.savings,
  }))
})
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-slate-900">Fluxo de Caixa — Últimos 12 Meses</h3>

    <div class="mb-4 flex gap-6 text-sm">
        <span class="flex items-center gap-2">
          <span class="h-3 w-3 rounded-full bg-emerald-500" />
          Receitas
        </span>
        <span class="flex items-center gap-2">
          <span class="h-3 w-3 rounded-full bg-rose-500" />
          Despesas
        </span>
        <span class="flex items-center gap-2">
          <span class="h-3 w-3 rounded-full bg-blue-500" />
          Poupança
        </span>
    </div>

    <div class="flex items-end gap-1.5" style="height: 200px">
      <div v-for="(item, idx) in chartData" :key="idx" class="flex flex-1 flex-col justify-end">
        <div class="mx-auto mb-1 text-xs text-slate-500">{{ item.savingsRate.toFixed(0) }}%</div>
        <div class="space-y-0.5" style="height: 180px">
          <div
            class="w-full rounded-t-sm bg-emerald-500 transition-all"
            :style="{ height: `${item.income}%` }"
            :title="`Receita: R$ ${item.rawIncome.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`"
          />
          <div
            class="w-full rounded-b-sm bg-rose-500 transition-all"
            :style="{ height: `${item.expenses}%` }"
            :title="`Despesa: R$ ${item.rawExpenses.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`"
          />
        </div>
        <p class="mt-1 text-center text-xs text-slate-400">{{ item.month }}</p>
      </div>
    </div>
  </div>
</template>
