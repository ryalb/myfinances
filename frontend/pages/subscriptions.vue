<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: subscriptions } = await useFetch<
  {
    id: number
    name: string
    category: string
    amount: number
    due_day: number
    is_active: boolean
    payments: {
      id: number
      due_date: string
      paid_date: string | null
      status: string
      paid_amount: number | null
    }[]
  }[]
>(`${config.public.apiBaseUrl}/subscriptions/`, { key: 'subscriptions-page', headers })

const categoryLabels: Record<string, string> = {
  utilities: 'Utilidades',
  internet: 'Internet',
  phone: 'Telefone',
  streaming: 'Streaming',
  other: 'Outro',
}

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'Pendente', color: 'bg-amber-100 text-amber-700' },
  paid: { label: 'Pago', color: 'bg-emerald-100 text-emerald-700' },
  overdue: { label: 'Atrasado', color: 'bg-rose-100 text-rose-700' },
}

const uiStore = useUiStore()
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Assinaturas e pagamentos recorrentes</h1>

    <div v-if="!subscriptions?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:repeat" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma assinatura cadastrada.</p>
      <p class="mt-1 text-sm text-sepia-400">Gerencie seus gastos recorrentes aqui.</p>
    </div>

    <div v-else class="space-y-4">
      <div v-for="sub in subscriptions" :key="sub.id" class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ sub.name }}</h3>
            <span class="mt-1 inline-block rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-600">
              {{ categoryLabels[sub.category] || sub.category }}
            </span>
          </div>
          <div class="text-right">
            <p :class="['text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">{{ formatBRL(sub.amount) }}</p>
            <p class="text-xs text-sepia-500">Vencimento: dia {{ sub.due_day }}</p>
          </div>
        </div>

        <div v-if="sub.payments?.length" class="mt-4">
          <h4 class="mb-2 text-sm font-medium text-sepia-700">Histórico de pagamentos</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="border-b border-sepia-200 bg-sepia-50">
                <tr>
                  <th class="px-3 py-2 text-left font-medium text-sepia-600">Vencimento</th>
                  <th class="px-3 py-2 text-left font-medium text-sepia-600">Status</th>
                  <th class="px-3 py-2 text-right font-medium text-sepia-600">Valor</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="payment in sub.payments.slice(0, 6)" :key="payment.id" class="border-b border-sepia-100 last:border-0">
                  <td class="px-3 py-2 text-sepia-500">{{ new Date(payment.due_date).toLocaleDateString('pt-BR') }}</td>
                  <td class="px-3 py-2">
                    <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusLabels[payment.status]?.color || 'bg-sepia-100 text-sepia-600']">
                      {{ statusLabels[payment.status]?.label || payment.status }}
                    </span>
                  </td>
                  <td :class="['px-3 py-2 text-right font-medium text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
                    {{ payment.paid_amount ? formatBRL(payment.paid_amount) : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
