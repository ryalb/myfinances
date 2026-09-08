<script setup lang="ts">
import { formatBRL } from '@/composables/useCurrency'
import { useUiStore } from '@/stores/ui'
import Popover from 'primevue/popover'

const props = defineProps<{
  netWorth: number
  assets: number
  liabilities: number
  history: { date: string; net_worth: number }[]
  breakdown: {
    cash: number
    investments: number
    pension: number
    debts: number
    creditCards: number
  }
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

// Racional do calculo de Ativos/Passivos (build_user_financial_summary no
// backend): cada total e a soma destas categorias, nunca um numero avulso.
const assetsBreakdown = computed(() => [
  { label: 'Caixa', value: props.breakdown.cash },
  { label: 'Investimentos', value: props.breakdown.investments },
  { label: 'Previdência', value: props.breakdown.pension },
])

const liabilitiesBreakdown = computed(() => [
  { label: 'Cartões de crédito', value: props.breakdown.creditCards },
  { label: 'Dívidas', value: props.breakdown.debts },
])

const assetsPopover = ref()
const liabilitiesPopover = ref()
const assetsBlock = ref()
const liabilitiesBlock = ref()
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
        <div ref="assetsBlock">
          <dt>
            <button
              type="button"
              class="flex items-center gap-1 text-xs uppercase tracking-wide text-sepia-400 hover:text-sepia-600"
              @click="(event) => assetsPopover.toggle(event, assetsBlock)"
            >
              Ativos
              <Icon icon="mdi:information-outline" class="h-3 w-3" />
            </button>
          </dt>
          <dd :class="['mt-1 font-mono text-lg font-semibold text-sepia-800', blur]">{{ formatBRL(assets) }}</dd>
        </div>
        <div ref="liabilitiesBlock">
          <dt>
            <button
              type="button"
              class="flex items-center gap-1 text-xs uppercase tracking-wide text-sepia-400 hover:text-sepia-600"
              @click="(event) => liabilitiesPopover.toggle(event, liabilitiesBlock)"
            >
              Passivos
              <Icon icon="mdi:information-outline" class="h-3 w-3" />
            </button>
          </dt>
          <dd :class="['mt-1 font-mono text-lg font-semibold text-vermelho-700', blur]">{{ formatBRL(liabilities) }}</dd>
        </div>
      </dl>
    </div>

    <Popover ref="assetsPopover">
      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-sepia-400">Composição dos ativos</p>
      <ul class="min-w-56 w-max space-y-2 text-sm">
        <li v-for="item in assetsBreakdown" :key="item.label" class="grid grid-cols-[1fr_auto] items-baseline gap-x-6">
          <span class="whitespace-nowrap text-sepia-500">{{ item.label }}</span>
          <span class="text-right font-mono text-sepia-800">{{ formatBRL(item.value) }}</span>
        </li>
      </ul>
    </Popover>

    <Popover ref="liabilitiesPopover">
      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-sepia-400">Composição dos passivos</p>
      <ul class="min-w-56 w-max space-y-2 text-sm">
        <li v-for="item in liabilitiesBreakdown" :key="item.label" class="grid grid-cols-[1fr_auto] items-baseline gap-x-6">
          <span class="whitespace-nowrap text-sepia-500">{{ item.label }}</span>
          <span class="text-right font-mono text-sepia-800">{{ formatBRL(item.value) }}</span>
        </li>
      </ul>
    </Popover>
  </div>
</template>
