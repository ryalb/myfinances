<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  label: string
  value: string
  sublabel?: string
  tone?: 'azul' | 'vermelho' | 'amber' | 'neutral'
  formula?: string
}>()

const uiStore = useUiStore()

const toneClass: Record<string, string> = {
  azul: 'text-azul-700',
  vermelho: 'text-vermelho-700',
  amber: 'text-amber-700',
  neutral: 'text-sepia-900',
}

const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))
</script>

<template>
  <article class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
    <p class="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-sepia-400">
      {{ label }}
      <Icon v-if="formula" icon="mdi:information-outline" class="h-3.5 w-3.5 cursor-help text-sepia-300" :title="formula" />
    </p>
    <p :class="['mt-2 font-mono text-2xl font-bold', toneClass[props.tone || 'neutral'], blur]">{{ value }}</p>
    <p :class="['mt-1 text-xs text-sepia-500', blur]">{{ sublabel }}</p>
  </article>
</template>
