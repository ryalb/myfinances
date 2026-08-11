<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import { formatIsoDate } from '@/composables/useDateFormat'

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

const statusColors: Record<string, string> = {
  active: 'bg-sepia-100 text-sepia-700',
  achieved: 'bg-emerald-100 text-emerald-700',
  paused: 'bg-sepia-100 text-sepia-600',
}

const uiStore = useUiStore()
</script>

<template>
  <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <h4 class="font-semibold text-sepia-900">{{ goal.name }}</h4>
        <span :class="['mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium', statusColors[goal.status] || 'bg-sepia-100 text-sepia-600']">
          {{ goal.status }}
        </span>
      </div>
      <p :class="['text-right text-sm text-sepia-500', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
        {{ formatBRL(goal.current_amount) }} / {{ formatBRL(goal.target_amount) }}
      </p>
    </div>

    <!-- Progress bar -->
    <div class="mt-3 h-3 w-full overflow-hidden rounded-full bg-sepia-100">
      <div
        class="h-full rounded-full bg-sepia-500 transition-all"
        :style="{ width: `${Math.min(goal.progress_percentage, 100)}%` }"
      />
    </div>

    <div class="mt-2 flex items-center justify-between text-xs text-sepia-500">
      <span>{{ goal.progress_percentage.toFixed(1) }} concluído</span>
      <span v-if="goal.target_date">{{ formatIsoDate(goal.target_date) }}</span>
    </div>
  </div>
</template>
