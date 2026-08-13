<script setup lang="ts">
import { formatBRL, formatPercent } from '@/composables/useCurrency'
import { useUiStore } from '@/stores/ui'

type Segment = {
  key: string
  label: string
  value: number
  percentage: number
  estimated?: boolean
}

const props = defineProps<{ segments: Segment[] }>()

const uiStore = useUiStore()
const blurClass = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

// Tons decrescentes de sepia na mesma ordem dos segmentos (maior alocacao
// primeiro, ja resolvido por quem monta `segments`) -- nao cor categorica: a
// carteira e composicao, nao tem sinal positivo/negativo para reservar
// azul/vermelho.
const TONE_STEPS = [
  'bg-sepia-800',
  'bg-sepia-700',
  'bg-sepia-600',
  'bg-sepia-500',
  'bg-sepia-400',
  'bg-sepia-300',
  'bg-sepia-200',
  'bg-sepia-100',
]

const toneClass = (index: number) => TONE_STEPS[index % TONE_STEPS.length]
</script>

<template>
  <div>
    <div class="flex h-3 w-full overflow-hidden rounded-full border border-sepia-200">
      <div
        v-for="(segment, index) in props.segments"
        :key="segment.key"
        :class="toneClass(index)"
        :style="{ width: `${segment.percentage}%` }"
        :title="`${segment.label}: ${formatPercent(segment.percentage)}`"
      />
    </div>

    <ul class="mt-4 grid gap-2 sm:grid-cols-2">
      <li
        v-for="(segment, index) in props.segments"
        :key="segment.key"
        class="flex items-center justify-between gap-3 text-sm"
      >
        <span class="flex items-center gap-2 text-sepia-700">
          <span :class="['h-2.5 w-2.5 shrink-0 rounded-full', toneClass(index)]" />
          {{ segment.label }}
          <span
            v-if="segment.estimated"
            class="rounded-full bg-sepia-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sepia-500"
            title="Categoria estimada pelo código do ativo"
          >
            estimado
          </span>
        </span>
        <span class="flex items-baseline gap-2 whitespace-nowrap font-mono">
          <span :class="['text-sepia-900', blurClass]">{{ formatBRL(segment.value) }}</span>
          <span class="text-xs text-sepia-400">{{ formatPercent(segment.percentage) }}</span>
        </span>
      </li>
    </ul>
  </div>
</template>
