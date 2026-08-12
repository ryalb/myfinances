<script setup lang="ts">
import Button from 'primevue/button'
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import { extractApiError } from '@/composables/useApi'
import type { Subscription, SubscriptionPayment } from '@/composables/useSubscriptions'
import { todayLocalISO } from '@/composables/useSubscriptions'

definePageMeta({
  middleware: 'auth',
})

const {
  subscriptions,
  refresh,
  updateSubscription,
  deleteSubscription,
  reconcileSubscriptions,
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
const reconciling = ref(false)
const expandedId = ref<number | null>(null)
const toggleExpand = (id: number) => {
  expandedId.value = expandedId.value === id ? null : id
}

const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

// A API devolve `payments` do vencimento mais futuro para o mais antigo
// (`Meta.ordering = ["-due_date"]`). `.slice(0, 6)` direto nessa lista mostrava só
// os vencimentos mais distantes no futuro -- sempre "pendente", nunca o que já foi
// pago. Aqui pega uma janela contígua em ordem cronológica ascendente ancorada em
// hoje (o mais passado possível dentro de 6 itens, com os próximos vencimentos
// completando quando a assinatura for nova e não tiver histórico ainda) e exibe em
// ordem decrescente -- uma única direção, sem alternar passado/futuro no meio.
const recentPayments = (sub: Subscription): SubscriptionPayment[] => {
  const today = todayLocalISO()
  const chronological = [...sub.payments].sort((a, b) => a.due_date.localeCompare(b.due_date))
  const firstUpcomingIndex = chronological.findIndex(p => p.due_date > today)
  const pastCount = firstUpcomingIndex === -1 ? chronological.length : firstUpcomingIndex
  const start = Math.max(0, pastCount - 6)
  return chronological.slice(start, start + 6).reverse()
}

// Badge da listagem principal: status do ciclo atual (o vencimento mais
// recente até hoje, ou o primeiro futuro se a assinatura ainda não venceu
// nenhuma vez) -- é o que responde "essa assinatura está ok?" de cara, sem
// precisar expandir o histórico.
const currentStatusBadge = (sub: Subscription): { label: string; color: string } => {
  if (!sub.is_active || !sub.payments.length) return { label: '—', color: 'bg-sepia-100 text-sepia-400' }
  const today = todayLocalISO()
  const chronological = [...sub.payments].sort((a, b) => a.due_date.localeCompare(b.due_date))
  const current = [...chronological].reverse().find(p => p.due_date <= today) ?? chronological[0]
  return statusBadge(current.status)
}

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

const reconcileNow = async () => {
  reconciling.value = true
  await run(reconcileSubscriptions, 'Erro ao reconciliar as assinaturas.')
  reconciling.value = false
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Assinaturas e pagamentos recorrentes</h1>
        <p class="mt-1 text-sepia-600">Cadastre despesas fixas. Pagamentos de contas conectadas são cruzados com suas transações automaticamente; marque manualmente os que não vêm de instituição conectada.</p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <Button
          class="inline-flex items-center gap-2 !rounded-lg !border !border-sepia-300 !bg-white !px-4 !py-2 !text-sm !font-medium !text-sepia-700 !whitespace-nowrap hover:!bg-sepia-50"
          :disabled="reconciling"
          @click="reconcileNow"
        >
          <Icon :icon="reconciling ? 'mdi:loading' : 'mdi:refresh'" :class="['h-4 w-4', reconciling && 'animate-spin']" />
          {{ reconciling ? 'Reconciliando...' : 'Reconciliar agora' }}
        </Button>
        <Button
          class="inline-flex items-center gap-2 !rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950"
          @click="openCreate"
        >
          <Icon icon="mdi:plus" class="h-4 w-4" />
          Nova assinatura
        </Button>
      </div>
    </div>

    <p v-if="error" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ error }}
    </p>

    <div v-if="!subscriptions?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:repeat" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma assinatura cadastrada.</p>
      <p class="mt-1 text-sm text-sepia-400">Cadastre a primeira para acompanhar vencimentos e pagamentos.</p>
    </div>

    <div v-else class="overflow-hidden rounded-lg border border-sepia-200 bg-white shadow-sm">
      <table class="w-full text-sm">
        <thead class="border-b border-sepia-200 bg-sepia-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Assinatura</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Status</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Categoria</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Vencimento</th>
            <th class="px-4 py-3 text-right font-medium text-sepia-600">Valor</th>
            <th class="px-4 py-3 text-right font-medium text-sepia-600">Ações</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="sub in subscriptions" :key="sub.id">
            <tr :class="['border-b border-sepia-100 last:border-0', sub.is_active ? '' : 'opacity-60']">
              <td class="px-4 py-3">
                <button
                  type="button"
                  class="flex items-center gap-1.5 text-left font-medium text-sepia-900 hover:text-sepia-700"
                  @click="toggleExpand(sub.id)"
                >
                  <Icon :icon="expandedId === sub.id ? 'mdi:chevron-down' : 'mdi:chevron-right'" class="h-4 w-4 shrink-0 text-sepia-400" />
                  {{ sub.name }}
                </button>
                <span v-if="!sub.is_active" class="ml-5.5 mt-0.5 inline-block rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-500">
                  Inativa
                </span>
              </td>
              <td class="px-4 py-3">
                <span :class="['inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', currentStatusBadge(sub).color]">
                  {{ currentStatusBadge(sub).label }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="inline-block whitespace-nowrap rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-600">
                  {{ categoryLabel(sub.category) }}
                </span>
              </td>
              <td class="px-4 py-3 text-sepia-500">dia {{ sub.due_day }}</td>
              <td :class="['px-4 py-3 text-right font-mono font-medium text-sepia-900', blur]">{{ formatBRL(sub.amount) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
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
                    class="!text-sepia-400 hover:!text-vermelho-600"
                    @click="remove(sub)"
                  >
                    <Icon icon="mdi:trash-can-outline" class="h-5 w-5" />
                  </Button>
                </div>
              </td>
            </tr>
            <tr v-if="expandedId === sub.id" class="border-b border-sepia-100 bg-sepia-50/50 last:border-0">
              <td colspan="6" class="px-4 py-4">
                <template v-if="sub.payments?.length">
                  <h4 class="mb-2 text-sm font-medium text-sepia-700">Histórico de pagamentos</h4>
                  <div class="overflow-hidden rounded-lg border border-sepia-200 bg-white">
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
                        <tr v-for="payment in recentPayments(sub)" :key="payment.id" class="border-b border-sepia-100 last:border-0">
                          <td class="px-3 py-2 text-sepia-500">{{ formatDueDate(payment.due_date) }}</td>
                          <td class="px-3 py-2">
                            <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusBadge(payment.status).color]">
                              {{ statusBadge(payment.status).label }}
                            </span>
                            <p v-if="payment.matched_transaction" class="mt-1 text-xs text-sepia-400">
                              via {{ payment.matched_transaction.description }}
                              <template v-if="payment.matched_transaction.account_name">· {{ payment.matched_transaction.account_name }}</template>
                            </p>
                          </td>
                          <td :class="['px-3 py-2 text-right font-mono font-medium text-sepia-900', blur]">
                            {{ payment.paid_amount ? formatBRL(payment.paid_amount) : '—' }}
                          </td>
                          <td class="px-3 py-2 text-right">
                            <Button
                              text
                              :disabled="busyPayment === payment.id"
                              :class="[
                                '!px-2 !py-1 !text-xs !font-medium',
                                payment.status === 'paid' ? '!text-sepia-500 hover:!text-sepia-700' : '!text-azul-600 hover:!text-azul-700',
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
                </template>
                <p v-else class="text-sm text-sepia-400">Sem histórico de pagamentos ainda.</p>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <subscriptions-subscription-form-modal
      v-model:open="showForm"
      :subscription="editing"
      @saved="refresh"
    />
  </section>
</template>
