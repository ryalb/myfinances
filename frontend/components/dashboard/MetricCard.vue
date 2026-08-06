<script setup lang="ts">
const props = defineProps<{
  label: string
  value: string
  sublabel?: string
  icon?: string
  color?: string
}>()

const colors: Record<string, string> = {
  emerald: 'text-emerald-600 bg-emerald-50',
  blue: 'text-blue-600 bg-blue-50',
  amber: 'text-amber-600 bg-amber-50',
  rose: 'text-rose-600 bg-rose-50',
  violet: 'text-violet-600 bg-violet-50',
  slate: 'text-slate-600 bg-slate-50',
}

const colorClass = colors[props.color || 'slate']
</script>

<template>
  <article class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
    <div class="flex items-center justify-between">
      <p class="text-sm font-medium text-slate-500">{{ label }}</p>
      <span v-if="icon" :class="['inline-flex items-center justify-center rounded-lg p-2', colorClass]">
        <Icon :icon="icon" class="h-5 w-5" />
      </span>
    </div>
    <p class="mt-3 text-2xl font-bold text-slate-900">{{ value }}</p>
    <p v-if="sublabel" class="mt-1 text-xs text-slate-400">{{ sublabel }}</p>
  </article>
</template>
