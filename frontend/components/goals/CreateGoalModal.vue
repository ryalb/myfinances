<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits(['created'])
const { createGoal } = useGoals()

const showModal = ref(false)
const name = ref('')
const targetAmount = ref('')
const currentAmount = ref('0')
const targetDate = ref('')
const loading = ref(false)
const error = ref('')

const handleSubmit = async () => {
  if (!name.value || !targetAmount.value) {
    error.value = 'Nome e valor alvo são obrigatórios.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await createGoal({
      name: name.value,
      target_amount: parseFloat(targetAmount.value),
      current_amount: parseFloat(currentAmount.value) || 0,
      target_date: targetDate.value || undefined,
    })
    showModal.value = false
    name.value = ''
    targetAmount.value = ''
    currentAmount.value = '0'
    targetDate.value = ''
    emit('created')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erro ao criar meta.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <button
      class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
      @click="showModal = true"
    >
      <Icon icon="mdi:plus" class="h-4 w-4" />
      Nova Meta
    </button>

    <!-- Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Transition name="slide">
            <div v-if="showModal" class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
              <div class="mb-4 flex items-center justify-between">
                <h3 class="text-lg font-semibold text-slate-900">Nova Meta Financeira</h3>
                <button class="text-slate-400 hover:text-slate-600" @click="showModal = false">
                  <Icon icon="mdi:close" class="h-5 w-5" />
                </button>
              </div>

              <div class="space-y-4">
                <div>
                  <label class="mb-1 block text-sm font-medium text-slate-700">Nome da meta</label>
                  <input
                    v-model="name"
                    type="text"
                    placeholder="Ex: Aposentadoria, Viagem..."
                    class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                </div>

                <div>
                  <label class="mb-1 block text-sm font-medium text-slate-700">Valor alvo (R$)</label>
                  <input
                    v-model="targetAmount"
                    type="number"
                    step="0.01"
                    placeholder="100000"
                    class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                </div>

                <div>
                  <label class="mb-1 block text-sm font-medium text-slate-700">Valor atual (R$)</label>
                  <input
                    v-model="currentAmount"
                    type="number"
                    step="0.01"
                    placeholder="0"
                    class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                </div>

                <div>
                  <label class="mb-1 block text-sm font-medium text-slate-700">Data alvo</label>
                  <input
                    v-model="targetDate"
                    type="date"
                    class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                </div>

                <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

                <div class="flex justify-end gap-2">
                  <button
                    class="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
                    @click="showModal = false"
                  >
                    Cancelar
                  </button>
                  <button
                    :disabled="loading"
                    class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                    @click="handleSubmit"
                  >
                    {{ loading ? 'Salvando...' : 'Salvar' }}
                  </button>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
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
