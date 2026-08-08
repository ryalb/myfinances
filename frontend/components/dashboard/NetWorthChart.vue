<script setup lang="ts">
const props = defineProps<{
  data: { date: string; net_worth: number; assets: number; liabilities: number }[]
}>()

const chartData = computed(() => {
  if (!props.data.length) return []
  const maxVal = Math.max(...props.data.map((d) => d.net_worth), 1)
  const minVal = Math.min(...props.data.map((d) => d.net_worth), 0)
  const range = maxVal - minVal || 1

  return props.data.map((d) => ({
    date: new Date(d.date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
    value: ((d.net_worth - minVal) / range) * 100,
  }))
})
</script>

<template>
  <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
    <h3 class="mb-4 text-lg font-semibold text-sepia-900">Evolução do Patrimônio Líquido</h3>

    <div v-if="chartData.length" class="relative" style="height: 200px">
      <!-- Area fill -->
      <svg class="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="netWorthGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#8b7355" stop-opacity="0.3" />
            <stop offset="100%" stop-color="#8b7355" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path
          :d="`M0,100 ${chartData.map((d, i) => `L${(i / (chartData.length - 1)) * 100},${100 - d.value}`).join(' ')} L100,100 Z`"
          fill="url(#netWorthGrad)"
        />
        <polyline
          :points="chartData.map((d, i) => `${(i / (chartData.length - 1)) * 100},${100 - d.value}`).join(' ')"
          fill="none"
          stroke="#8b7355"
          stroke-width="0.8"
        />
      </svg>

      <!-- Data points -->
      <div class="absolute inset-0 flex items-end justify-between">
        <div v-for="(item, idx) in chartData" :key="idx" class="group relative flex flex-1 justify-center">
          <div
            class="h-2 w-2 rounded-full bg-sepia-500 opacity-0 transition-opacity group-hover:opacity-100"
            :style="{ marginBottom: `${item.value}%` }"
          />
          <div
            class="absolute bottom-full mb-2 hidden rounded bg-sepia-900 px-2 py-1 text-xs text-white whitespace-nowrap group-hover:block"
          >
             {{ item.date }}: {{ formatBRL(props.data[idx]?.net_worth ?? 0) }}
          </div>
        </div>
      </div>
    </div>

    <p v-else class="py-8 text-center text-sm text-sepia-400">Sem dados suficientes para mostrar a evolução.</p>
  </div>
</template>
