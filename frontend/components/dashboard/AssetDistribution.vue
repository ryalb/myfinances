<script setup lang="ts">
const props = defineProps<{
  breakdown: {
    cash: number
    investments: number
    pension: number
    debts: number
    creditCards: number
  }
}>()

const items = computed(() => [
  { label: 'Caixa', value: props.breakdown.cash, color: 'bg-emerald-500' },
  { label: 'Investimentos', value: props.breakdown.investments, color: 'bg-blue-500' },
  { label: 'Previdência', value: props.breakdown.pension, color: 'bg-violet-500' },
  { label: 'Dívidas', value: props.breakdown.debts, color: 'bg-rose-500' },
  { label: 'Cartões', value: props.breakdown.creditCards, color: 'bg-amber-500' },
].filter((i) => i.value > 0))

const total = computed(() => items.value.reduce((sum, i) => sum + Math.abs(i.value), 0))
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-slate-900">Composição do Patrimônio</h3>

    <!-- Stacked bar -->
    <div v-if="items.length" class="mb-4 flex h-6 w-full overflow-hidden rounded-full">
      <div
        v-for="item in items"
        :key="item.label"
        :class="[item.color, 'transition-all']"
        :style="{ width: `${(Math.abs(item.value) / total) * 100}%` }"
        :title="`${item.label}: R$ ${Math.abs(item.value).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`"
      />
    </div>

    <!-- Legend -->
    <div class="space-y-2">
      <div v-for="item in items" :key="item.label" class="flex items-center justify-between text-sm">
        <span class="flex items-center gap-2">
          <span :class="[item.color, 'block h-3 w-3 rounded-full']" />
          <span class="text-slate-600">{{ item.label }}</span>
        </span>
        <span class="font-medium text-slate-900">
          R$ {{ Math.abs(item.value).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }}
          <span class="text-slate-400">({{ ((Math.abs(item.value) / total) * 100).toFixed(1) }}%)</span>
        </span>
      </div>
    </div>
  </div>
</template>
