<script setup lang="ts">
import { formatBRL, formatPercent } from '@/composables/useCurrency'
import { useUiStore } from '@/stores/ui'
import { CHART_OTHER_COLOR, CHART_PALETTE } from '@/composables/useChartPalette'

export type DonutSegment = {
  key: string
  label: string
  value: number
  // Cor fixa por entidade (ex.: categoria) -- sem isso, a cor vem da posicao.
  color?: string
  to?: string
}

const props = withDefaults(
  defineProps<{
    segments: DonutSegment[]
    centerLabel?: string
    // Mais fatias que isso viram "Outros": rosca so funciona para parte-do-todo
    // com poucas partes; o detalhe completo fica na tabela/legenda da pagina.
    maxSegments?: number
  }>(),
  { centerLabel: '', maxSegments: 6 },
)

const uiStore = useUiStore()
const blurClass = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const NuxtLink = resolveComponent('NuxtLink')

const RADIUS = 40
const STROKE = 14
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
// Respiro entre fatias, em unidades do viewBox.
const GAP = 1.2

const normalized = computed(() => {
  const positive = props.segments.filter((s) => s.value > 0).sort((a, b) => b.value - a.value)
  const withColors = positive.map((s, i) => ({ ...s, color: s.color || CHART_PALETTE[i % CHART_PALETTE.length] }))
  if (withColors.length <= props.maxSegments) return withColors
  const head = withColors.slice(0, props.maxSegments - 1)
  const tail = withColors.slice(props.maxSegments - 1)
  return [
    ...head,
    {
      key: '__other',
      label: `Outros (${tail.length})`,
      value: tail.reduce((sum, s) => sum + s.value, 0),
      color: CHART_OTHER_COLOR,
      to: undefined,
    },
  ]
})

const total = computed(() => normalized.value.reduce((sum, s) => sum + s.value, 0))

const arcs = computed(() => {
  let offset = 0
  const single = normalized.value.length === 1
  return normalized.value.map((segment) => {
    const fraction = total.value > 0 ? segment.value / total.value : 0
    const length = fraction * CIRCUMFERENCE
    const visible = single ? length : Math.max(length - GAP, 0.01)
    const arc = {
      ...segment,
      percentage: fraction * 100,
      dasharray: `${visible} ${CIRCUMFERENCE - visible}`,
      dashoffset: -offset,
    }
    offset += length
    return arc
  })
})

const hovered = ref<string | null>(null)
const hoveredArc = computed(() => arcs.value.find((a) => a.key === hovered.value) || null)
</script>

<template>
  <div class="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
    <div class="relative h-40 w-40 shrink-0">
      <svg viewBox="0 0 100 100" class="h-full w-full -rotate-90" role="img" :aria-label="centerLabel || 'Distribuição'">
        <circle cx="50" cy="50" :r="RADIUS" fill="none" stroke="#f5eedd" :stroke-width="STROKE" />
        <circle
          v-for="arc in arcs"
          :key="arc.key"
          cx="50"
          cy="50"
          :r="RADIUS"
          fill="none"
          :stroke="arc.color"
          :stroke-width="hovered === arc.key ? STROKE + 3 : STROKE"
          :stroke-dasharray="arc.dasharray"
          :stroke-dashoffset="arc.dashoffset"
          :opacity="hovered && hovered !== arc.key ? 0.35 : 1"
          class="cursor-pointer transition-all duration-150"
          @mouseenter="hovered = arc.key"
          @mouseleave="hovered = null"
        >
          <title>{{ arc.label }}: {{ formatPercent(arc.percentage) }}</title>
        </circle>
      </svg>
      <div class="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
        <template v-if="hoveredArc">
          <span class="line-clamp-2 text-[11px] leading-tight text-sepia-500">{{ hoveredArc.label }}</span>
          <span class="font-mono text-base font-semibold text-sepia-900">{{ formatPercent(hoveredArc.percentage) }}</span>
        </template>
        <template v-else>
          <span v-if="centerLabel" class="text-[11px] uppercase tracking-wide text-sepia-400">{{ centerLabel }}</span>
          <span :class="['font-mono text-sm font-semibold text-sepia-900', blurClass]">{{ formatBRL(total) }}</span>
        </template>
      </div>
    </div>

    <ul class="w-full min-w-0 flex-1 space-y-1.5">
      <li
        v-for="arc in arcs"
        :key="arc.key"
        :class="['rounded-md px-2 py-1 text-sm transition-colors', hovered === arc.key ? 'bg-sepia-50' : '']"
        @mouseenter="hovered = arc.key"
        @mouseleave="hovered = null"
      >
        <component
          :is="arc.to ? NuxtLink : 'div'"
          :to="arc.to"
          class="flex items-center justify-between gap-3 !text-sepia-700 hover:!text-sepia-900"
        >
          <span class="flex min-w-0 items-center gap-2">
            <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: arc.color }" />
            <span class="truncate">{{ arc.label }}</span>
            <Icon v-if="arc.to" icon="mdi:chevron-right" class="h-4 w-4 shrink-0 text-sepia-400" />
          </span>
          <span class="flex items-baseline gap-2 whitespace-nowrap font-mono">
            <span :class="['text-sepia-900', blurClass]">{{ formatBRL(arc.value) }}</span>
            <span class="w-14 text-right text-xs text-sepia-500">{{ formatPercent(arc.percentage) }}</span>
          </span>
        </component>
      </li>
    </ul>
  </div>
</template>
