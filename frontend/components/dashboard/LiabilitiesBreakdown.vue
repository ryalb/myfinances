<script setup lang="ts">
const props = defineProps<{
  totalLiabilities: number
  creditCards: number
  otherDebts: number
}>()

const items = computed(() => [
  { label: 'Cartões de crédito', value: props.creditCards, color: 'bg-amber-500' },
  { label: 'Outras dívidas', value: props.otherDebts, color: 'bg-rose-500' },
].filter((i) => i.value > 0))

const total = computed(() => items.value.reduce((sum, i) => sum + Math.abs(i.value), 0))
</script>

<template>
  <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-sepia-900">Passivos</h3>

    <div v-if="items.length" class="mb-4 flex h-6 w-full overflow-hidden rounded-full">
      <div
        v-for="item in items"
        :key="item.label"
        :class="[item.color, 'transition-all']"
        :style="{ width: `${(Math.abs(item.value) / total) * 100}%` }"
         :title="`${item.label}: ${formatBRL(Math.abs(item.value))}`"
      />
    </div>

    <div v-if="!items.length" class="py-6 text-center text-sm text-sepia-400">
      Nenhum passivo identificado.
    </div>

    <div class="space-y-2">
      <div v-for="item in items" :key="item.label" class="flex items-center justify-between text-sm">
        <span class="flex items-center gap-2">
          <span :class="[item.color, 'block h-3 w-3 rounded-full']" />
          <span class="text-sepia-600">{{ item.label }}</span>
        </span>
        <span class="font-medium text-sepia-900">
           {{ formatBRL(Math.abs(item.value)) }}
          <span v-if="total > 0" class="text-sepia-400">({{ ((Math.abs(item.value) / total) * 100).toFixed(1) }}%)</span>
        </span>
      </div>
    </div>
  </div>
</template>
