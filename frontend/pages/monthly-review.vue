<script setup lang="ts">
import Button from 'primevue/button'
import { formatBRL } from '@/composables/useCurrency'
import { extractApiError } from '@/composables/useApi'
import { useUiStore } from '@/stores/ui'

definePageMeta({
  middleware: 'auth',
})

const uiStore = useUiStore()
const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const {
  summary,
  loading,
  year,
  month,
  isCurrentMonth,
  previousMonth,
  nextMonth,
  saveAdjustments,
  markCompleted,
} = useMonthlyReview()

const MONTH_NAMES = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]
const MONTH_SHORT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

const monthLabel = computed(() => `${MONTH_NAMES[month.value - 1]} de ${year.value}`)

const error = ref('')

// Pré-preenche os 3 campos com os ajustes já salvos deste mês; troca de mês
// (ou o primeiro load) reabastece a partir do que veio do backend.
const adjustmentInputs = ref<string[]>(['', '', ''])
watch(
  () => summary.value?.review.adjustments,
  (saved) => {
    adjustmentInputs.value = [saved?.[0] ?? '', saved?.[1] ?? '', saved?.[2] ?? '']
  },
  { immediate: true },
)

const savingAdjustments = ref(false)
const onSaveAdjustments = async () => {
  savingAdjustments.value = true
  error.value = ''
  try {
    const adjustments = adjustmentInputs.value.map((v) => v.trim()).filter(Boolean)
    await saveAdjustments(adjustments)
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao salvar os ajustes.')
  } finally {
    savingAdjustments.value = false
  }
}

const togglingCompleted = ref(false)
const onToggleCompleted = async () => {
  togglingCompleted.value = true
  error.value = ''
  try {
    await markCompleted(!summary.value?.review.completed_at)
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao marcar o mês como revisado.')
  } finally {
    togglingCompleted.value = false
  }
}

const trendItems = computed(() => {
  const trend = summary.value?.savings_rate_trend ?? []
  return trend.map((item, idx) => ({
    ...item,
    label: `${MONTH_SHORT[item.month - 1]}/${String(item.year).slice(2)}`,
    isReviewedMonth: idx === trend.length - 1,
  }))
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold">Revisão mensal</h1>
        <p class="mt-1 text-sepia-600">
          Um ritual de ~20 minutos: patrimônio, poupança, comportamento e os 3 ajustes do próximo mês.
        </p>
      </div>
      <div class="flex items-center gap-2 rounded-lg border border-sepia-200 bg-white px-2 py-1 shadow-sm">
        <button
          type="button"
          class="rounded-md p-1.5 text-sepia-500 hover:bg-sepia-100"
          @click="previousMonth"
        >
          <Icon icon="mdi:chevron-left" class="h-5 w-5" />
        </button>
        <span class="min-w-[10rem] text-center text-sm font-medium text-sepia-900">{{ monthLabel }}</span>
        <button
          type="button"
          :disabled="isCurrentMonth"
          class="rounded-md p-1.5 text-sepia-500 hover:bg-sepia-100 disabled:opacity-30 disabled:hover:bg-transparent"
          @click="nextMonth"
        >
          <Icon icon="mdi:chevron-right" class="h-5 w-5" />
        </button>
      </div>
    </div>

    <p v-if="error" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ error }}
    </p>

    <div v-if="loading && !summary" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:loading" class="mx-auto mb-3 h-8 w-8 animate-spin text-sepia-400" />
      <p class="text-sepia-500">Calculando a revisão do mês...</p>
    </div>

    <template v-else-if="summary">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Patrimônio ao final do mês</p>
          <p :class="['mt-2 font-mono text-2xl font-bold text-sepia-900', blur]">
            {{ summary.current_net_worth === null ? '—' : formatBRL(summary.current_net_worth) }}
          </p>
          <p
            v-if="summary.net_worth_delta !== null"
            :class="['mt-1 text-sm', blur, summary.net_worth_delta >= 0 ? 'text-azul-600' : 'text-vermelho-600']"
          >
            {{ summary.net_worth_delta >= 0 ? '+' : '' }}{{ formatBRL(summary.net_worth_delta) }} no mês
          </p>
          <p v-else class="mt-1 text-xs text-sepia-400">
            Sem histórico suficiente para comparar com o mês anterior.
          </p>
        </article>

        <article class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="mb-2 text-xs font-medium uppercase tracking-wide text-sepia-400">Tendência de poupança (6 meses)</p>
          <div class="space-y-2">
            <div v-for="item in trendItems" :key="`${item.year}-${item.month}`" class="flex items-center gap-3">
              <span :class="['w-12 text-xs', item.isReviewedMonth ? 'font-semibold text-sepia-900' : 'text-sepia-500']">
                {{ item.label }}
              </span>
              <div class="h-2 flex-1 rounded-full bg-sepia-100">
                <div
                  :class="item.savings_rate >= 0 ? 'bg-azul-600' : 'bg-vermelho-600'"
                  class="h-2 rounded-full transition-all"
                  :style="{ width: `${Math.min(Math.abs(item.savings_rate), 100)}%` }"
                />
              </div>
              <span
                :class="[
                  'w-14 shrink-0 text-right font-mono text-xs',
                  item.savings_rate >= 0 ? 'text-azul-700' : 'text-vermelho-700',
                ]"
              >
                {{ item.savings_rate.toFixed(0) }}%
              </span>
            </div>
          </div>
        </article>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-3 flex items-center gap-2 text-base font-semibold text-sepia-900">
            <Icon icon="mdi:swap-vertical" class="h-5 w-5 text-sepia-700" />
            Gasto por categoria vs. mês anterior
          </h3>
          <ul v-if="summary.category_deltas.length" class="space-y-2">
            <li
              v-for="item in summary.category_deltas"
              :key="item.category"
              class="flex items-center justify-between text-sm"
            >
              <span class="text-sepia-700">{{ item.category }}</span>
              <span
                :class="[
                  'font-mono',
                  blur,
                  item.delta > 0 ? 'text-vermelho-600' : item.delta < 0 ? 'text-azul-600' : 'text-sepia-400',
                ]"
              >
                {{ item.delta > 0 ? '+' : '' }}{{ formatBRL(item.delta) }}
              </span>
            </li>
          </ul>
          <p v-else class="text-sm text-sepia-400">Sem gastos neste mês ou no anterior para comparar.</p>
        </div>

        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-3 flex items-center gap-2 text-base font-semibold text-sepia-900">
            <Icon icon="mdi:star-outline" class="h-5 w-5 text-azul-600" />
            Conquistas do mês
          </h3>
          <ul v-if="summary.achievements.length" class="space-y-2">
            <li v-for="(item, idx) in summary.achievements" :key="idx" class="flex gap-2 text-sm text-sepia-700">
              <Icon icon="mdi:check-circle-outline" class="mt-0.5 h-4 w-4 shrink-0 text-azul-600" />
              <span>{{ item }}</span>
            </li>
          </ul>
          <p v-else class="text-sm text-sepia-400">Nenhuma conquista notável este mês.</p>
        </div>
      </div>

      <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">3 ajustes para o próximo mês</h3>
        <p class="mb-3 text-xs text-sepia-400">
          Poucos e específicos: o que você vai realmente mudar, não uma lista de boas intenções.
        </p>
        <div class="space-y-2">
          <input
            v-for="(_, idx) in adjustmentInputs"
            :key="idx"
            v-model="adjustmentInputs[idx]"
            type="text"
            :placeholder="`Ajuste ${idx + 1}`"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <Button
          :disabled="savingAdjustments"
          class="!mt-3 !rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950 disabled:!opacity-50"
          @click="onSaveAdjustments"
        >
          {{ savingAdjustments ? 'Salvando...' : 'Salvar ajustes' }}
        </Button>
      </div>

      <div class="flex flex-col items-start justify-between gap-3 rounded-lg border border-sepia-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center">
        <div>
          <p class="text-sm font-medium text-sepia-900">
            {{ summary.review.completed_at ? 'Mês revisado' : 'Ainda não revisado' }}
          </p>
          <p v-if="summary.review.completed_at" class="text-xs text-sepia-400">
            Marcado em {{ new Date(summary.review.completed_at).toLocaleDateString('pt-BR') }}.
          </p>
        </div>
        <Button
          :disabled="togglingCompleted"
          class="shrink-0 !rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950"
          @click="onToggleCompleted"
        >
          {{ summary.review.completed_at ? 'Desmarcar revisão' : 'Marcar mês como revisado' }}
        </Button>
      </div>
    </template>
  </section>
</template>
