<script setup lang="ts">
import Button from 'primevue/button'
import { extractApiError } from '@/composables/useApi'
import { formatBRL } from '@/composables/useCurrency'
import type { PensionPlan } from '@/composables/usePensionPlans'
import { useUiStore } from '@/stores/ui'

definePageMeta({
  middleware: 'auth',
})

const { plans, createPlan, updatePlan, deletePlan } = usePensionPlans()
const uiStore = useUiStore()

const form = reactive({ name: '', provider: '', balance: '' })
const saving = ref(false)
const error = ref('')
const busyId = ref<number | null>(null)

const editingId = ref<number | null>(null)
const editForm = reactive({ name: '', provider: '', balance: '' })

const run = async (action: () => Promise<void>, fallback: string) => {
  error.value = ''
  try {
    await action()
  } catch (e: unknown) {
    error.value = extractApiError(e, fallback)
  }
}

const submit = async () => {
  const balance = Number(form.balance)
  if (!form.name.trim() || !form.provider.trim()) {
    error.value = 'Informe o nome do plano e a seguradora/provedor.'
    return
  }
  if (!Number.isFinite(balance) || balance < 0) {
    error.value = 'Informe um saldo válido.'
    return
  }

  saving.value = true
  await run(async () => {
    await createPlan({ name: form.name.trim(), provider: form.provider.trim(), balance })
    form.name = ''
    form.provider = ''
    form.balance = ''
  }, 'Erro ao adicionar o plano.')
  saving.value = false
}

const startEdit = (plan: PensionPlan) => {
  editingId.value = plan.id
  editForm.name = plan.name
  editForm.provider = plan.provider
  editForm.balance = String(plan.balance)
}

const cancelEdit = () => {
  editingId.value = null
}

const saveEdit = async (plan: PensionPlan) => {
  const balance = Number(editForm.balance)
  if (!editForm.name.trim() || !editForm.provider.trim()) {
    error.value = 'Informe o nome do plano e a seguradora/provedor.'
    return
  }
  if (!Number.isFinite(balance) || balance < 0) {
    error.value = 'Informe um saldo válido.'
    return
  }

  busyId.value = plan.id
  await run(async () => {
    await updatePlan(plan.id, {
      name: editForm.name.trim(),
      provider: editForm.provider.trim(),
      balance,
    })
    editingId.value = null
  }, 'Erro ao editar o plano.')
  busyId.value = null
}

const remove = async (plan: PensionPlan) => {
  if (!window.confirm(`Excluir o plano "${plan.name}"?`)) return
  busyId.value = plan.id
  await run(() => deletePlan(plan.id), 'Erro ao excluir o plano.')
  busyId.value = null
}
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Previdência privada</h1>
      <p class="mt-1 text-sepia-600">
        PGBL e VGBL ficam no Open Insurance, fora do Open Finance que sincroniza o resto da
        carteira — por isso não chegam automaticamente. Cadastre manualmente e atualize o saldo
        quando quiser.
      </p>
    </div>

    <p v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ error }}
    </p>

    <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-3 text-base font-semibold text-sepia-900">Adicionar plano manualmente</h3>
      <div class="grid gap-3 sm:grid-cols-[2fr_2fr_1fr_auto] sm:items-end">
        <div>
          <label class="mb-1 block text-sm font-medium text-sepia-700">Nome do plano</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="Ex: PGBL Rico"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-sepia-700">Seguradora/provedor</label>
          <input
            v-model="form.provider"
            type="text"
            placeholder="Ex: Icatu Seguros"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-sepia-700">Saldo atual</label>
          <input
            v-model="form.balance"
            type="number"
            min="0"
            step="0.01"
            placeholder="0,00"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <Button
          :disabled="saving"
          class="!rounded-lg !bg-sepia-600 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-700 disabled:!opacity-50"
          @click="submit"
        >
          {{ saving ? 'Salvando...' : 'Adicionar' }}
        </Button>
      </div>
    </div>

    <div v-if="!plans?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:shield-account" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum plano de previdência encontrado.</p>
      <p class="mt-1 text-sm text-sepia-400">Adicione um plano manualmente acima.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <article
        v-for="plan in plans"
        :key="plan.id"
        class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm"
      >
        <div v-if="editingId === plan.id" class="space-y-3">
          <div>
            <label class="mb-1 block text-sm font-medium text-sepia-700">Nome do plano</label>
            <input
              v-model="editForm.name"
              type="text"
              class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
            >
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-sepia-700">Seguradora/provedor</label>
            <input
              v-model="editForm.provider"
              type="text"
              class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
            >
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-sepia-700">Saldo atual</label>
            <input
              v-model="editForm.balance"
              type="number"
              min="0"
              step="0.01"
              class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
            >
          </div>
          <div class="flex items-center justify-end gap-1">
            <Button
              text
              rounded
              :disabled="busyId === plan.id"
              title="Salvar"
              class="!text-emerald-600 hover:!text-emerald-700"
              @click="saveEdit(plan)"
            >
              <Icon icon="mdi:check" class="h-5 w-5" />
            </Button>
            <Button
              text
              rounded
              :disabled="busyId === plan.id"
              title="Cancelar"
              class="!text-sepia-400 hover:!text-sepia-700"
              @click="cancelEdit"
            >
              <Icon icon="mdi:close" class="h-5 w-5" />
            </Button>
          </div>
        </div>

        <div v-else class="flex items-start justify-between gap-3">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ plan.name }}</h3>
            <p class="mt-1 text-sm text-sepia-500">{{ plan.provider }}</p>
            <span
              v-if="!plan.is_manual"
              class="mt-2 inline-block whitespace-nowrap rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-600"
            >
              Sincronizado via Open Finance
            </span>
          </div>
          <div class="flex flex-col items-end gap-2">
            <p :class="['text-right text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
              {{ formatBRL(plan.balance) }}
            </p>
            <div v-if="plan.is_manual" class="flex items-center gap-1">
              <Button
                text
                rounded
                :disabled="busyId === plan.id"
                title="Editar"
                class="!text-sepia-400 hover:!text-sepia-700"
                @click="startEdit(plan)"
              >
                <Icon icon="mdi:pencil-outline" class="h-5 w-5" />
              </Button>
              <Button
                text
                rounded
                :disabled="busyId === plan.id"
                title="Excluir"
                class="!text-sepia-400 hover:!text-rose-600"
                @click="remove(plan)"
              >
                <Icon icon="mdi:trash-can-outline" class="h-5 w-5" />
              </Button>
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
