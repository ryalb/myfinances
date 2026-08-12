<script setup lang="ts">
import Button from 'primevue/button'
import { extractApiError } from '@/composables/useApi'
import { SUBSCRIPTION_CATEGORY_OPTIONS } from '@/composables/useSubscriptionLabels'
import type { Subscription } from '@/composables/useSubscriptions'

const props = defineProps<{
  open: boolean
  subscription?: Subscription | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: []
}>()

const { createSubscription, updateSubscription } = useSubscriptions()
const { get } = useApi()

const { data: accounts } = await useAsyncData(
  'subscription-form-accounts',
  async () => (await get<{ id: number; name: string }[]>('/accounts/')) || [],
  { default: () => [] },
)

const isEditing = computed(() => Boolean(props.subscription))

const form = reactive({
  name: '',
  category: 'other',
  amount: '',
  dueDay: '',
  paymentAccount: '' as string,
  isActive: true,
})

const loading = ref(false)
const error = ref('')

// O modal é montado uma vez e reaproveitado, então os campos precisam ser
// recarregados a cada abertura -- senão editar uma assinatura e abrir "nova"
// depois mostraria os dados da anterior.
watch(
  () => [props.open, props.subscription?.id],
  () => {
    if (!props.open) return
    error.value = ''
    const sub = props.subscription
    form.name = sub?.name ?? ''
    form.category = sub?.category ?? 'other'
    form.amount = sub ? String(sub.amount) : ''
    form.dueDay = sub ? String(sub.due_day) : ''
    form.paymentAccount = sub?.payment_account ? String(sub.payment_account) : ''
    form.isActive = sub?.is_active ?? true
  },
  { immediate: true },
)

const close = () => emit('update:open', false)

const handleSubmit = async () => {
  const amount = Number.parseFloat(form.amount)
  const dueDay = Number.parseInt(form.dueDay, 10)

  if (!form.name.trim()) {
    error.value = 'Informe um nome para a assinatura.'
    return
  }
  if (!Number.isFinite(amount) || amount <= 0) {
    error.value = 'Informe um valor mensal maior que zero.'
    return
  }
  if (!Number.isInteger(dueDay) || dueDay < 1 || dueDay > 31) {
    error.value = 'O dia de vencimento precisa estar entre 1 e 31.'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const payload = {
      name: form.name.trim(),
      category: form.category,
      amount,
      due_day: dueDay,
      is_active: form.isActive,
      payment_account: form.paymentAccount ? Number.parseInt(form.paymentAccount, 10) : null,
    }
    if (props.subscription) {
      await updateSubscription(props.subscription.id, payload)
    } else {
      await createSubscription(payload)
    }
    close()
    emit('saved')
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao salvar a assinatura.')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <Transition name="slide">
          <div v-if="open" class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div class="mb-4 flex items-center justify-between">
              <h3 class="text-lg font-semibold text-sepia-900">
                {{ isEditing ? 'Editar assinatura' : 'Nova assinatura' }}
              </h3>
              <Button text rounded class="!text-sepia-400 hover:!text-sepia-600" @click="close">
                <Icon icon="mdi:close" class="h-5 w-5" />
              </Button>
            </div>

            <div class="space-y-4">
              <div>
                <label class="mb-1 block text-sm font-medium text-sepia-700">Nome</label>
                <input
                  v-model="form.name"
                  type="text"
                  placeholder="Ex: Conta de água, Netflix..."
                  class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                >
              </div>

              <div>
                <label class="mb-1 block text-sm font-medium text-sepia-700">Categoria</label>
                <select
                  v-model="form.category"
                  class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                >
                  <option v-for="option in SUBSCRIPTION_CATEGORY_OPTIONS" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>

              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="mb-1 block text-sm font-medium text-sepia-700">Valor mensal (R$)</label>
                  <input
                    v-model="form.amount"
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="120.00"
                    class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                  >
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium text-sepia-700">Dia de vencimento</label>
                  <input
                    v-model="form.dueDay"
                    type="number"
                    min="1"
                    max="31"
                    placeholder="10"
                    class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                  >
                </div>
              </div>

              <div>
                <label class="mb-1 block text-sm font-medium text-sepia-700">
                  Conta de pagamento
                  <span class="font-normal text-sepia-400">(opcional)</span>
                </label>
                <select
                  v-model="form.paymentAccount"
                  class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                >
                  <option value="">Nenhuma</option>
                  <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
                    {{ account.name }}
                  </option>
                </select>
              </div>

              <label class="flex items-center gap-2 text-sm text-sepia-700">
                <input v-model="form.isActive" type="checkbox" class="rounded border-sepia-300 text-sepia-600 focus:ring-sepia-500">
                Assinatura ativa
              </label>

              <p v-if="error" class="text-sm text-vermelho-600">{{ error }}</p>

              <div class="flex justify-end gap-2">
                <Button class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950" @click="close">
                  Cancelar
                </Button>
                <Button
                  :disabled="loading"
                  class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950 disabled:!opacity-50"
                  @click="handleSubmit"
                >
                  {{ loading ? 'Salvando...' : 'Salvar' }}
                </Button>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateY(20px);
}
</style>
