<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  label: string
  value: string
  sublabel?: string
  icon?: string
  color?: string
}>()

const uiStore = useUiStore()

const colors: Record<string, string> = {
  emerald: 'text-emerald-600 bg-emerald-50',
  blue: 'text-sepia-600 bg-sepia-50',
  amber: 'text-amber-600 bg-amber-50',
  rose: 'text-rose-600 bg-rose-50',
  violet: 'text-sepia-600 bg-sepia-50',
  slate: 'text-sepia-600 bg-sepia-50',
}

const colorClass = colors[props.color || 'slate']
</script>

<template>
  <article class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
    <div class="flex items-center justify-between">
      <p class="text-sm font-medium text-sepia-500">{{ label }}</p>
      <span v-if="icon" :class="['inline-flex items-center justify-center rounded-lg p-2', colorClass]">
        <Icon :icon="icon" class="h-5 w-5" />
      </span>
    </div>
    <p :class="['mt-3 text-2xl font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">{{ value }}</p>
    <p :class="['mt-1 text-xs text-sepia-400', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">{{ sublabel }}</p>
  </article>
</template>
