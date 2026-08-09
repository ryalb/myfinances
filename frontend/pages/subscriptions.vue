<script setup lang="ts">
import Button from 'primevue/button'
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import { extractApiError } from '@/composables/useApi'
import type { Subscription } from '@/composables/useSubscriptions'

definePageMeta({
  middleware: 'auth',
})

const {
  subscriptions,
  refresh,
  updateSubscription,
  deleteSubscription,
  markPaid,
  markPending,
} = useSubscriptions()

const { categoryLabel, statusBadge, formatDueDate } = useSubscriptionLabels()
const uiStore = useUiStore()

const showForm = ref(false)
const editing = ref<Subscription | null>(null)
const error = ref('')
// Trava por pagamento, não global: uma linha em voo não deve desabilitar as
// outras nem sumir com a página inteira.
const busyPayment = ref<number | null>(null)
const busySubscription = ref<number | null>(null)

const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const openCreate = () => {
  editing.value = null
  showForm.value = true
}

const openEdit = (sub: Subscription) => {
  editing.value = sub
  showForm.value = true
}

const run = async (action: () => Promise<void>, fallback: string) => {
  error.value = ''
  try {
    await action()
  } catch (e: unknown) {
    error.value = extractApiError(e, fallback)
  }
}

const togglePayment = async (paymentId: number, status: string) => {
  busyPayment.value = paymentId
  await run(
    () => (status === 'paid' ? markPending(paymentId) : markPaid(paymentId)),
    'Erro ao atualizar o pagamento.',
  )
  busyPayment.value = null
}

const toggleActive = async (sub: Subscription) => {
  busySubscription.value = sub.id
  await run(
    () => updateSubscription(sub.id, { is_active: !sub.is_active }),
    'Erro ao atualizar a assinatura.',
  )
  busySubscription.value = null
}

const remove = async (sub: Subscription) => {
  if (!window.confirm(`Excluir "${sub.name}"? O histórico de pagamentos vai junto.`)) return
  busySubscription.value = sub.id
  await run(() => deleteSubscription(sub.id), 'Erro ao excluir a assinatura.')
  busySubscription.value = null
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Assinaturas e pagamentos recorrentes</h1>
        <p class="mt-1 text-sepia-600">Cadastre despesas fixas e marque os pagamentos que não vêm de instituição conectada.</p>
      </div>
      <Button
        class="inline-flex items-center gap-2 !rounded-lg !bg-sepia-600 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-700"
        @click="openCreate"
      >
        <Icon icon="mdi:plus" class="h-4 w-4" />
        Nova assinatura
      </Button>
    </div>

    <p v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ error }}
    </p>

    <div v-if="!subscriptions?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:repeat" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma assinatura cadastrada.</p>
      <p class="mt-1 text-sm text-sepia-400">Cadastre a primeira para acompanhar vencimentos e pagamentos.</p>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="sub in subscriptions"
        :key="sub.id"
        :class="['rounded-xl border bg-white p-5 shadow-sm', sub.is_active ? 'border-sepia-200' : 'border-sepia-200 opacity-60']"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ sub.name }}</h3>
            <div class="mt-1 flex items-center gap-2">
              <span class="inline-block rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-600">
                {{ categoryLabel(sub.category) }}
              </span>
              <span v-if="!sub.is_active" class="inline-block rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-500">
                Inativa
              </span>
            </div>
          </div>

          <div class="flex items-start gap-4">
            <div class="text-right">
              <p :class="['text-lg font-bold text-sepia-900', blur]">{{ formatBRL(sub.amount) }}</p>
              <p class="text-xs text-sepia-500">Vencimento: dia {{ sub.due_day }}</p>
            </div>
            <div class="flex items-center gap-1">
              <Button
                text
                rounded
                :disabled="busySubscription === sub.id"
                :title="sub.is_active ? 'Desativar' : 'Reativar'"
                class="!text-sepia-400 hover:!text-sepia-700"
                @click="toggleActive(sub)"
              >
                <Icon :icon="sub.is_active ? 'mdi:pause-circle-outline' : 'mdi:play-circle-outline'" class="h-5 w-5" />
              </Button>
              <Button
                text
                rounded
                title="Editar"
                class="!text-sepia-400 hover:!text-sepia-700"
                @click="openEdit(sub)"
              >
                <Icon icon="mdi:pencil-outline" class="h-5 w-5" />
              </Button>
              <Button
                text
                rounded
                :disabled="busySubscription === sub.id"
                title="Excluir"
                class="!text-sepia-400 hover:!text-rose-600"
                @click="remove(sub)"
              >
                <Icon icon="mdi:trash-can-outline" class="h-5 w-5" />
              </Button>
            </div>
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
                  <th class="px-3 py-2 text-right font-medium text-sepia-600">Ação</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="payment in sub.payments.slice(0, 6)" :key="payment.id" class="border-b border-sepia-100 last:border-0">
                  <td class="px-3 py-2 text-sepia-500">{{ formatDueDate(payment.due_date) }}</td>
                  <td class="px-3 py-2">
                    <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusBadge(payment.status).color]">
                      {{ statusBadge(payment.status).label }}
                    </span>
                  </td>
                  <td :class="['px-3 py-2 text-right font-medium text-sepia-900', blur]">
                    {{ payment.paid_amount ? formatBRL(payment.paid_amount) : '—' }}
                  </td>
                  <td class="px-3 py-2 text-right">
                    <Button
                      text
                      :disabled="busyPayment === payment.id"
                      :class="[
                        '!px-2 !py-1 !text-xs !font-medium',
                        payment.status === 'paid' ? '!text-sepia-500 hover:!text-sepia-700' : '!text-emerald-600 hover:!text-emerald-700',
                      ]"
                      @click="togglePayment(payment.id, payment.status)"
                    >
                      {{ busyPayment === payment.id ? '...' : payment.status === 'paid' ? 'Desmarcar' : 'Marcar pago' }}
                    </Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <subscriptions-subscription-form-modal
      v-model:open="showForm"
      :subscription="editing"
      @saved="refresh"
    />
  </section>
</template>
