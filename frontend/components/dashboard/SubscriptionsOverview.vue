<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import type { SubscriptionOverview } from '@/composables/useSubscriptionOverview'

const props = defineProps<{
  overview: SubscriptionOverview
}>()

const uiStore = useUiStore()
const { categoryLabel, formatDueDate } = useSubscriptionLabels()

const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const totals = computed(() => [
  {
    label: 'Total recorrente',
    value: props.overview.monthlyRecurringTotal,
    sublabel: `${props.overview.activeCount} ${props.overview.activeCount === 1 ? 'assinatura ativa' : 'assinaturas ativas'}`,
    color: 'text-sepia-900',
  },
  {
    label: 'Pago no mês',
    value: props.overview.paidThisMonth,
    sublabel: 'Já debitado',
    color: 'text-azul-700',
  },
  {
    label: 'Pendente no mês',
    value: props.overview.pendingThisMonth,
    sublabel: 'A pagar até o fim do mês',
    color: 'text-amber-600',
  },
])

const hasNothing = computed(() => props.overview.activeCount === 0)
</script>

<template>
  <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
    <div class="mb-4 flex items-center justify-between">
      <h3 class="text-base font-semibold text-sepia-900">Assinaturas e Recorrentes</h3>
      <NuxtLink to="/subscriptions" class="text-sm text-sepia-500 hover:text-sepia-700">
        Ver todas
      </NuxtLink>
    </div>

    <div v-if="hasNothing" class="py-6 text-center text-sm text-sepia-400">
      Nenhuma assinatura cadastrada.
    </div>

    <template v-else>
      <div class="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div v-for="total in totals" :key="total.label">
          <p class="text-xs uppercase tracking-wide text-sepia-400">{{ total.label }}</p>
          <p :class="['mt-1 font-mono text-xl font-bold', total.color, blur]">{{ formatBRL(total.value) }}</p>
          <p class="mt-0.5 text-xs text-sepia-500">{{ total.sublabel }}</p>
        </div>
      </div>

      <div v-if="overview.overdue.length" class="mb-5 rounded-lg border border-vermelho-200 bg-vermelho-50 p-4">
        <div class="mb-2 flex items-center justify-between">
          <span class="flex items-center gap-2 text-sm font-semibold text-vermelho-700">
            <Icon icon="mdi:alert-circle-outline" class="h-5 w-5" />
            {{ overview.overdue.length }} {{ overview.overdue.length === 1 ? 'pagamento atrasado' : 'pagamentos atrasados' }}
          </span>
          <span :class="['font-mono text-sm font-bold text-vermelho-700', blur]">{{ formatBRL(overview.overdueTotal) }}</span>
        </div>
        <ul class="space-y-1">
          <li v-for="item in overview.overdue" :key="`${item.name}-${item.dueDate}`" class="flex items-center justify-between text-sm">
            <span class="text-vermelho-800">
              {{ item.name }}
              <span class="text-vermelho-500">· venceu {{ formatDueDate(item.dueDate) }}</span>
            </span>
            <span :class="['font-mono font-medium text-vermelho-800', blur]">{{ formatBRL(item.amount) }}</span>
          </li>
        </ul>
      </div>

      <div>
        <h4 class="mb-2 text-sm font-medium text-sepia-700">Próximos vencimentos</h4>
        <p v-if="!overview.upcoming.length" class="py-3 text-center text-sm text-sepia-400">
          Nada a vencer nos próximos 30 dias.
        </p>
        <ul v-else class="divide-y divide-sepia-100">
          <li v-for="item in overview.upcoming" :key="`${item.name}-${item.dueDate}`" class="flex items-center justify-between py-2 text-sm">
            <span class="flex items-center gap-2">
              <span class="text-sepia-900">{{ item.name }}</span>
              <span class="inline-block whitespace-nowrap rounded-full bg-sepia-100 px-2 py-0.5 text-xs text-sepia-600">
                {{ categoryLabel(item.category) }}
              </span>
            </span>
            <span class="flex items-center gap-3">
              <span class="text-sepia-500">{{ formatDueDate(item.dueDate) }}</span>
              <span :class="['font-mono font-medium text-sepia-900', blur]">{{ formatBRL(item.amount) }}</span>
            </span>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>
