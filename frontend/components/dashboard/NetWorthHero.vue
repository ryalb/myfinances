<script setup lang="ts">
import { formatBRL } from '@/composables/useCurrency'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  netWorth: number
  assets: number
  liabilities: number
  history: { date: string; net_worth: number }[]
}>()

const uiStore = useUiStore()
const tally = useCountUp(props.netWorth)

const trend = computed(() => {
  if (props.history.length < 2) return null
  const first = props.history[0].net_worth
  const last = props.history[props.history.length - 1].net_worth
  return { delta: last - first, months: props.history.length, positive: last - first >= 0 }
})

const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))
</script>

<template>
  <div class="rounded-lg border border-sepia-200 bg-white px-6 py-8 shadow-sm sm:px-10 sm:py-10">
    <div class="flex flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-xs font-medium uppercase tracking-widest text-sepia-400">Patrimônio líquido</p>
        <p :class="['ledger-total-rule mt-2 inline-block pb-2 font-mono text-4xl font-bold text-sepia-900 sm:text-5xl', blur]">
          {{ formatBRL(tally) }}
        </p>
        <p v-if="trend" :class="['mt-3 text-sm font-medium', trend.positive ? 'text-azul-700' : 'text-vermelho-600']">
          {{ trend.positive ? '▲' : '▼' }} {{ formatBRL(Math.abs(trend.delta)) }} nos últimos {{ trend.months }} meses
        </p>
      </div>

      <dl class="grid grid-cols-2 gap-x-8 gap-y-2 sm:gap-x-12">
        <div>
          <dt class="text-xs uppercase tracking-wide text-sepia-400">Ativos</dt>
          <dd :class="['mt-1 font-mono text-lg font-semibold text-sepia-800', blur]">{{ formatBRL(assets) }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase tracking-wide text-sepia-400">Passivos</dt>
          <dd :class="['mt-1 font-mono text-lg font-semibold text-vermelho-700', blur]">{{ formatBRL(liabilities) }}</dd>
        </div>
      </dl>
    </div>
  </div>
</template>
