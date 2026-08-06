<script setup lang="ts">
defineProps<{
  goal: {
    id: number
    name: string
    target_amount: number
    current_amount: number
    target_date: string | null
    status: string
    progress_percentage: number
  }
}>()

const formatBRL = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

const statusColors: Record<string, string> = {
  active: 'bg-blue-100 text-blue-700',
  achieved: 'bg-emerald-100 text-emerald-700',
  paused: 'bg-slate-100 text-slate-600',
}
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <h4 class="font-semibold text-slate-900">{{ goal.name }}</h4>
        <span :class="['mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium', statusColors[goal.status] || 'bg-slate-100 text-slate-600']">
          {{ goal.status }}
        </span>
      </div>
      <p class="text-right text-sm text-slate-500">
        {{ formatBRL(goal.current_amount) }} / {{ formatBRL(goal.target_amount) }}
      </p>
    </div>

    <!-- Progress bar -->
    <div class="mt-3 h-3 w-full overflow-hidden rounded-full bg-slate-100">
      <div
        class="h-full rounded-full bg-indigo-500 transition-all"
        :style="{ width: `${Math.min(goal.progress_percentage, 100)}%` }"
      />
    </div>

    <div class="mt-2 flex items-center justify-between text-xs text-slate-500">
      <span>{{ goal.progress_percentage.toFixed(1) }} concluído</span>
      <span v-if="goal.target_date">{{ new Date(goal.target_date).toLocaleDateString('pt-BR') }}</span>
    </div>
  </div>
</template>
