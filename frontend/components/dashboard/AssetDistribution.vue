<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  breakdown: {
    cash: number
    investments: number
    pension: number
    debts: number
    creditCards: number
  }
}>()

const uiStore = useUiStore()

const items = computed(() => [
  { label: 'Caixa', value: props.breakdown.cash, color: 'bg-azul-500' },
  { label: 'Investimentos', value: props.breakdown.investments, color: 'bg-sepia-500' },
  { label: 'Previdência', value: props.breakdown.pension, color: 'bg-sepia-300' },
  { label: 'Dívidas', value: props.breakdown.debts, color: 'bg-vermelho-600' },
  { label: 'Cartões', value: props.breakdown.creditCards, color: 'bg-amber-500' },
].filter((i) => i.value > 0))

const total = computed(() => items.value.reduce((sum, i) => sum + Math.abs(i.value), 0))
</script>

<template>
  <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
    <h3 class="mb-3 text-base font-semibold text-sepia-900">Composição do Patrimônio</h3>

    <!-- Stacked bar -->
    <div v-if="items.length" class="mb-4 flex h-6 w-full overflow-hidden rounded-full">
      <div
        v-for="item in items"
        :key="item.label"
        :class="[item.color, 'transition-all']"
        :style="{ width: `${(Math.abs(item.value) / total) * 100}%` }"
         :title="`${item.label}: ${formatBRL(Math.abs(item.value))}`"
      />
    </div>

    <!-- Legend -->
    <div class="space-y-2">
      <div v-for="item in items" :key="item.label" class="flex items-center justify-between text-sm">
        <span class="flex items-center gap-2">
          <span :class="[item.color, 'block h-3 w-3 rounded-full']" />
          <span class="text-sepia-600">{{ item.label }}</span>
        </span>
        <span :class="['font-mono font-medium text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
          {{ formatBRL(Math.abs(item.value)) }}
          <span class="text-sepia-400">({{ ((Math.abs(item.value) / total) * 100).toFixed(1) }}%)</span>
        </span>
      </div>
    </div>
  </div>
</template>
