<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  currentNetWorth: number
  monthlySavings: number
  averageMonthlyExpenses: number
  targetNetWorth: number
  estimatedPassiveIncome: number
  financialRunwayMonths: number
  estimatedRetireDate: string | null
  monthsToFreedom: number
  targetReached: boolean
  conservativeMonths: number
  baseMonths: number
  aggressiveMonths: number
}>()

const uiStore = useUiStore()

const scenarioLabels: Record<string, { label: string; months: number; color: string; description: string }> = {
  conservative: {
    label: 'Conservador',
    months: props.conservativeMonths,
    color: 'bg-amber-500',
    description: 'Retorno estimado: 4% a.a.',
  },
  base: {
    label: 'Base',
    months: props.baseMonths,
    color: 'bg-sepia-500',
    description: 'Retorno estimado: 8% a.a.',
  },
  aggressive: {
    label: 'Agressivo',
    months: props.aggressiveMonths,
    color: 'bg-emerald-500',
    description: 'Retorno estimado: 12% a.a.',
  },
}

const monthsToYears = (m: number) => {
  if (m <= 0) return '0 anos'
  const years = Math.floor(m / 12)
  const months = m % 12
  return `${years}a ${months}m`
}

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
}
</script>

<template>
  <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-sepia-900">Liberdade Financeira</h3>

    <!-- Status -->
    <div
      :class="[
        'mb-4 rounded-lg p-4',
        targetReached ? 'bg-emerald-50 text-emerald-800' : 'bg-sepia-50 text-sepia-800',
      ]"
    >
      <p class="text-sm font-medium">
        {{ targetReached ? '🎉 Você atingiu sua meta de liberdade financeira!' : `Faltam ${monthsToYears(monthsToFreedom)} para a liberdade financeira` }}
      </p>
      <p v-if="estimatedRetireDate && !targetReached" class="mt-1 text-xs opacity-80">
        Previsão: {{ formatDate(estimatedRetireDate) }}
      </p>
    </div>

    <!-- Key metrics -->
    <div class="grid grid-cols-2 gap-3 mb-4">
      <div class="rounded-lg bg-sepia-50 p-3">
        <p class="text-xs text-sepia-500">Patrimônio atual</p>
        <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
           {{ formatBRL(currentNetWorth) }}
        </p>
      </div>
      <div class="rounded-lg bg-sepia-50 p-3">
        <p class="text-xs text-sepia-500">Meta de patrimônio</p>
        <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
           {{ formatBRL(targetNetWorth) }}
        </p>
      </div>
      <div class="rounded-lg bg-sepia-50 p-3">
        <p class="text-xs text-sepia-500">Poupança mensal média</p>
        <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
           {{ formatBRL(monthlySavings) }}
        </p>
      </div>
      <div class="rounded-lg bg-sepia-50 p-3">
        <p class="text-xs text-sepia-500">Despesa mensal média</p>
        <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
           {{ formatBRL(averageMonthlyExpenses) }}
        </p>
      </div>
      <div class="rounded-lg bg-sepia-50 p-3">
        <p class="text-xs text-sepia-500">Renda passiva estimada</p>
        <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
           {{ formatBRL(estimatedPassiveIncome) }}
        </p>
      </div>
      <div class="rounded-lg bg-sepia-50 p-3">
        <p class="text-xs text-sepia-500">Runway financeiro</p>
        <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
          {{ financialRunwayMonths >= 999 ? '∞' : `${financialRunwayMonths} meses` }}
        </p>
      </div>
    </div>

    <!-- Scenarios -->
    <h4 class="mb-3 text-sm font-medium text-sepia-700">Projeção por Cenário</h4>
    <div class="space-y-3">
      <div v-for="(scenario, key) in scenarioLabels" :key="key" class="space-y-1">
        <div class="flex items-center justify-between text-sm">
          <span class="text-sepia-600">{{ scenario.label }}</span>
          <span class="font-medium text-sepia-900">{{ monthsToYears(scenario.months) }}</span>
        </div>
        <div class="h-2 w-full overflow-hidden rounded-full bg-sepia-100">
          <div
            :class="[scenario.color, 'h-full rounded-full transition-all']"
            :style="{ width: `${Math.min((scenario.months / 360) * 100, 100)}%` }"
          />
        </div>
        <p class="text-xs text-sepia-400">{{ scenario.description }}</p>
      </div>
    </div>
  </div>
</template>
