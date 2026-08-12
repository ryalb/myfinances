<script setup lang="ts">
import Button from 'primevue/button'
import { extractApiError } from '@/composables/useApi'
import type { CategorizationRule } from '@/composables/useCategorizationRules'

definePageMeta({
  middleware: 'auth',
})

const { rules, createRule, updateRule, deleteRule, reapply } = useCategorizationRules()

const form = reactive({ pattern: '', category: '', priority: '100' })
const saving = ref(false)
const error = ref('')
const notice = ref('')
const busyRule = ref<number | null>(null)
const reapplying = ref(false)

const editingId = ref<number | null>(null)
const editForm = reactive({ pattern: '', category: '', priority: '100' })

const run = async (action: () => Promise<void>, fallback: string) => {
  error.value = ''
  notice.value = ''
  try {
    await action()
  } catch (e: unknown) {
    error.value = extractApiError(e, fallback)
  }
}

// O motor de regras roda na importação: criar ou editar uma regra sozinha não
// muda nada do que já está gravado. Reaplicar na hora, em vez de deixar isso para
// um segundo clique em "Reaplicar ao histórico", é o que faz o efeito aparecer.
const reapplyAndNotify = async (prefix = '') => {
  const updated = await reapply()
  const suffix
    = updated === 0
      ? 'Nenhum lançamento mudou de categoria.'
      : `${updated} ${updated === 1 ? 'lançamento recategorizado' : 'lançamentos recategorizados'}.`
  notice.value = prefix ? `${prefix} ${suffix}` : suffix
}

const submit = async () => {
  const priority = Number.parseInt(form.priority, 10)
  if (!form.pattern.trim() || !form.category.trim()) {
    error.value = 'Informe o texto a procurar e a categoria de destino.'
    return
  }
  if (!Number.isInteger(priority) || priority < 0) {
    error.value = 'A prioridade precisa ser um número inteiro não negativo.'
    return
  }

  saving.value = true
  await run(async () => {
    await createRule({
      pattern: form.pattern.trim(),
      category: form.category.trim(),
      priority,
    })
    form.pattern = ''
    form.category = ''
    form.priority = '100'
    await reapplyAndNotify('Regra criada.')
  }, 'Erro ao criar a regra.')
  saving.value = false
}

const toggleActive = async (rule: CategorizationRule) => {
  busyRule.value = rule.id
  await run(async () => {
    await updateRule(rule.id, { is_active: !rule.is_active })
    await reapplyAndNotify()
  }, 'Erro ao atualizar a regra.')
  busyRule.value = null
}

const remove = async (rule: CategorizationRule) => {
  if (!window.confirm(`Excluir a regra "${rule.pattern}"?`)) return
  busyRule.value = rule.id
  await run(() => deleteRule(rule.id), 'Erro ao excluir a regra.')
  busyRule.value = null
}

const startEdit = (rule: CategorizationRule) => {
  editingId.value = rule.id
  editForm.pattern = rule.pattern
  editForm.category = rule.category
  editForm.priority = String(rule.priority)
}

const cancelEdit = () => {
  editingId.value = null
}

const saveEdit = async (rule: CategorizationRule) => {
  const priority = Number.parseInt(editForm.priority, 10)
  if (!editForm.pattern.trim() || !editForm.category.trim()) {
    error.value = 'Informe o texto a procurar e a categoria de destino.'
    return
  }
  if (!Number.isInteger(priority) || priority < 0) {
    error.value = 'A prioridade precisa ser um número inteiro não negativo.'
    return
  }

  busyRule.value = rule.id
  await run(async () => {
    await updateRule(rule.id, {
      pattern: editForm.pattern.trim(),
      category: editForm.category.trim(),
      priority,
    })
    editingId.value = null
    await reapplyAndNotify('Regra atualizada.')
  }, 'Erro ao editar a regra.')
  busyRule.value = null
}

const runReapply = async () => {
  reapplying.value = true
  await run(() => reapplyAndNotify(), 'Erro ao reaplicar as regras.')
  reapplying.value = false
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold">Regras de categorização</h1>
        <p class="mt-1 text-sepia-600">
          Quando a descrição de um lançamento contém o texto da regra, ele recebe a categoria
          definida. Regras suas têm precedência sobre a categoria que vem do banco.
        </p>
      </div>
      <Button
        :disabled="reapplying || !rules?.length"
        class="shrink-0 !rounded-lg !bg-sepia-900 !px-3 !py-1.5 !text-xs !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950 disabled:!opacity-40"
        @click="runReapply"
      >
        {{ reapplying ? 'Reaplicando...' : 'Reaplicar ao histórico' }}
      </Button>
    </div>

    <p v-if="error" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ error }}
    </p>
    <p v-if="notice" class="rounded-lg border border-azul-200 bg-azul-50 px-4 py-3 text-sm text-azul-700">
      {{ notice }}
    </p>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-3 text-base font-semibold text-sepia-900">Nova regra</h3>
      <div class="grid gap-3 sm:grid-cols-[2fr_2fr_1fr_auto] sm:items-end">
        <div>
          <label class="mb-1 block text-sm font-medium text-sepia-700">Texto na descrição</label>
          <input
            v-model="form.pattern"
            type="text"
            placeholder="Ex: uber"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-sepia-700">Categoria</label>
          <input
            v-model="form.category"
            type="text"
            placeholder="Ex: transporte"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium text-sepia-700" title="Menor número decide primeiro">
            Prioridade
          </label>
          <input
            v-model="form.priority"
            type="number"
            min="0"
            class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          >
        </div>
        <Button
          :disabled="saving"
          class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950 disabled:!opacity-50"
          @click="submit"
        >
          {{ saving ? 'Salvando...' : 'Adicionar' }}
        </Button>
      </div>
      <p class="mt-2 text-xs text-sepia-400">
        Prioridade menor decide primeiro. Use um número baixo para regras específicas
        ("mercado livre") e alto para genéricas ("mercado").
      </p>
    </div>

    <div v-if="!rules?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:tag-multiple-outline" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma regra cadastrada.</p>
      <p class="mt-1 text-sm text-sepia-400">
        Sem regras, a categoria vem do banco ou de palavras-chave conhecidas.
      </p>
    </div>

    <div v-else class="overflow-hidden rounded-lg border border-sepia-200 bg-white shadow-sm">
      <table class="w-full text-sm">
        <thead class="border-b border-sepia-200 bg-sepia-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Prioridade</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Texto na descrição</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Categoria</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Status</th>
            <th class="px-4 py-3 text-right font-medium text-sepia-600">Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="rule in rules"
            :key="rule.id"
            :class="['border-b border-sepia-100 last:border-0', rule.is_active ? '' : 'opacity-50']"
          >
            <template v-if="editingId === rule.id">
              <td class="px-4 py-2">
                <input
                  v-model="editForm.priority"
                  type="number"
                  min="0"
                  class="w-20 rounded-lg border border-sepia-300 px-2 py-1.5 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                >
              </td>
              <td class="px-4 py-2">
                <input
                  v-model="editForm.pattern"
                  type="text"
                  class="w-full rounded-lg border border-sepia-300 px-2 py-1.5 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                >
              </td>
              <td class="px-4 py-2">
                <input
                  v-model="editForm.category"
                  type="text"
                  class="w-full rounded-lg border border-sepia-300 px-2 py-1.5 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
                >
              </td>
              <td class="px-4 py-3">
                <span
                  :class="[
                    'inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium',
                    rule.is_active ? 'bg-azul-100 text-azul-700' : 'bg-sepia-100 text-sepia-600',
                  ]"
                >
                  {{ rule.is_active ? 'Ativa' : 'Inativa' }}
                </span>
              </td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  <Button
                    text
                    rounded
                    :disabled="busyRule === rule.id"
                    title="Salvar"
                    class="!text-azul-600 hover:!text-azul-700"
                    @click="saveEdit(rule)"
                  >
                    <Icon icon="mdi:check" class="h-5 w-5" />
                  </Button>
                  <Button
                    text
                    rounded
                    :disabled="busyRule === rule.id"
                    title="Cancelar"
                    class="!text-sepia-400 hover:!text-sepia-700"
                    @click="cancelEdit"
                  >
                    <Icon icon="mdi:close" class="h-5 w-5" />
                  </Button>
                </div>
              </td>
            </template>
            <template v-else>
              <td class="px-4 py-3 text-sepia-500">{{ rule.priority }}</td>
              <td class="px-4 py-3 font-medium text-sepia-900">{{ rule.pattern }}</td>
              <td class="px-4 py-3">
                <span class="inline-block whitespace-nowrap rounded bg-sepia-100 px-2 py-0.5 text-xs text-sepia-600">
                  {{ rule.category }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span
                  :class="[
                    'inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium',
                    rule.is_active ? 'bg-azul-100 text-azul-700' : 'bg-sepia-100 text-sepia-600',
                  ]"
                >
                  {{ rule.is_active ? 'Ativa' : 'Inativa' }}
                </span>
              </td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  <Button
                    text
                    rounded
                    :disabled="busyRule === rule.id"
                    title="Editar"
                    class="!text-sepia-400 hover:!text-sepia-700"
                    @click="startEdit(rule)"
                  >
                    <Icon icon="mdi:pencil-outline" class="h-5 w-5" />
                  </Button>
                  <Button
                    text
                    rounded
                    :disabled="busyRule === rule.id"
                    :title="rule.is_active ? 'Desativar' : 'Reativar'"
                    class="!text-sepia-400 hover:!text-sepia-700"
                    @click="toggleActive(rule)"
                  >
                    <Icon :icon="rule.is_active ? 'mdi:pause-circle-outline' : 'mdi:play-circle-outline'" class="h-5 w-5" />
                  </Button>
                  <Button
                    text
                    rounded
                    :disabled="busyRule === rule.id"
                    title="Excluir"
                    class="!text-sepia-400 hover:!text-vermelho-600"
                    @click="remove(rule)"
                  >
                    <Icon icon="mdi:trash-can-outline" class="h-5 w-5" />
                  </Button>
                </div>
              </td>
            </template>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
