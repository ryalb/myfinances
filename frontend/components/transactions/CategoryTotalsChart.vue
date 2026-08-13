<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import type { CategoryTotal } from '@/composables/useTransactionStats'

const props = defineProps<{
  title: string
  items: CategoryTotal[]
  emptyMessage?: string
}>()

const uiStore = useUiStore()
const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

// Paleta categórica fixa (8 tons, ordem validada contra daltonismo e contraste) --
// nunca ciclada: da 8ª categoria em diante entra em "Outras" em vez de gerar um
// nono tom. As categorias já chegam ordenadas por total (maior primeiro), então
// a cor segue a posição no ranking, não um hash por nome.
const PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']
const OTHER_COLOR = '#cfb683' // sepia-300: mesmo neutro usado para o "resto" na composição do patrimônio.
const MAX_SLOTS = 7

type Row = CategoryTotal & { color: string }

const rows = computed<Row[]>(() => {
  const items = props.items
  if (items.length <= MAX_SLOTS + 1) {
    return items.map((item, index) => ({ ...item, color: PALETTE[index] }))
  }

  const top = items.slice(0, MAX_SLOTS).map((item, index) => ({ ...item, color: PALETTE[index] }))
  const rest = items.slice(MAX_SLOTS)
  const other: Row = {
    category: 'Outras',
    total: rest.reduce((sum, item) => sum + item.total, 0),
    count: rest.reduce((sum, item) => sum + item.count, 0),
    percentage: rest.reduce((sum, item) => sum + item.percentage, 0),
    color: OTHER_COLOR,
  }
  return [...top, other]
})

const total = computed(() => rows.value.reduce((sum, row) => sum + row.total, 0) || 1)

// Centro e raio do círculo (viewBox 0 0 100 100).
const CX = 50
const CY = 50
const R = 45
// Vão angular entre fatias -- mesma ideia do vão de 2px da barra empilhada
// (separa sem desenhar borda), só que em graus em vez de pixels.
const GAP_DEGREES = 1.5

const pointOnCircle = (angleDeg: number) => {
  const angleRad = (angleDeg * Math.PI) / 180
  return {
    x: CX + R * Math.sin(angleRad),
    y: CY - R * Math.cos(angleRad),
  }
}

type Slice = Row & { path: string }

// Fatias em `<path>`, não um hack de `<circle>` com `stroke-dasharray` --
// mais direto de ler e não depende de um raio de traço enganando o olho para
// parecer uma pizza cheia. Ângulo 0° é meio-dia (12h), sentido horário --
// convenção padrão de gráfico de pizza.
const slices = computed<Slice[]>(() => {
  let cumulative = 0
  return rows.value.map((row) => {
    const span = (row.total / total.value) * 360
    const start = cumulative
    const end = cumulative + span
    cumulative = end

    const gap = Math.min(GAP_DEGREES, span / 4)
    const p1 = pointOnCircle(start + gap)
    const p2 = pointOnCircle(end - gap)
    const largeArcFlag = end - start - 2 * gap > 180 ? 1 : 0

    return {
      ...row,
      path: `M ${CX},${CY} L ${p1.x.toFixed(3)},${p1.y.toFixed(3)} A ${R},${R} 0 ${largeArcFlag},1 ${p2.x.toFixed(3)},${p2.y.toFixed(3)} Z`,
    }
  })
})

const sliceLabel = (row: Row) => `${row.category}: ${formatBRL(row.total)} (${row.percentage.toFixed(1)}%)`
</script>

<template>
  <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
    <h3 class="mb-3 text-base font-semibold text-sepia-900">{{ title }}</h3>

    <div v-if="!rows.length" class="py-8 text-center text-sm text-sepia-400">
      {{ emptyMessage || 'Sem lançamentos para estes filtros.' }}
    </div>

    <div v-else class="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <svg viewBox="0 0 100 100" class="h-40 w-40 shrink-0">
        <!-- Uma única categoria enche o círculo inteiro -- um arco de 360° é
        degenerado em SVG, então esse caso vira um círculo cheio em vez de um "path". -->
        <circle v-if="rows.length === 1" :cx="CX" :cy="CY" :r="R" :fill="rows[0].color">
          <title>{{ sliceLabel(rows[0]) }}</title>
        </circle>
        <path v-for="slice in slices" v-else :key="slice.category" :d="slice.path" :fill="slice.color">
          <title>{{ sliceLabel(slice) }}</title>
        </path>
      </svg>

      <div class="w-full min-w-0 space-y-2">
        <div v-for="row in rows" :key="row.category" class="flex items-center justify-between gap-3 text-sm">
          <span class="flex min-w-0 items-center gap-2">
            <span class="block h-3 w-3 shrink-0 rounded-full" :style="{ backgroundColor: row.color }" />
            <span class="truncate text-sepia-600">{{ row.category }}</span>
            <span class="shrink-0 text-xs text-sepia-400">({{ row.count }})</span>
          </span>
          <span :class="['shrink-0 whitespace-nowrap font-mono font-medium text-sepia-900', blur]">
            {{ formatBRL(row.total) }}
            <span class="text-sepia-400">({{ row.percentage.toFixed(1) }}%)</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
