<script setup lang="ts">
import { VERDICT_LABELS, type VerdictStatus } from '@/composables/useInvestmentPerformance'

const props = withDefaults(
  defineProps<{ status: VerdictStatus; count?: number; size?: 'sm' | 'md' }>(),
  { count: undefined, size: 'md' },
)

// Azul/vermelho seguem a convencao do app para positivo/negativo; icone junto
// para o estado nunca depender so da cor.
const STYLES: Record<VerdictStatus, { classes: string; icon: string }> = {
  keep: { classes: 'bg-azul-50 text-azul-700 border-azul-200', icon: 'mdi:check-circle-outline' },
  watch: { classes: 'bg-amber-50 text-amber-800 border-amber-200', icon: 'mdi:alert-outline' },
  review: { classes: 'bg-vermelho-50 text-vermelho-700 border-vermelho-200', icon: 'mdi:alert-octagon-outline' },
  unknown: { classes: 'bg-sepia-50 text-sepia-500 border-sepia-200', icon: 'mdi:help-circle-outline' },
}

const style = computed(() => STYLES[props.status])
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1 whitespace-nowrap rounded-full border font-medium',
      size === 'sm' ? 'px-1.5 py-0.5 text-[11px]' : 'px-2 py-0.5 text-xs',
      style.classes,
    ]"
  >
    <Icon :icon="style.icon" :class="size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'" />
    <template v-if="count !== undefined">{{ count }} · </template>{{ VERDICT_LABELS[status] }}
  </span>
</template>
