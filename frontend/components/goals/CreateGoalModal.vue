<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import { toIsoDateString } from '@/composables/useDateFormat'

const emit = defineEmits(['created'])
const { createGoal } = useGoals()

const showModal = ref(false)
const name = ref('')
const targetAmount = ref<number | null>(null)
const currentAmount = ref<number | null>(0)
const targetDate = ref<Date | null>(null)
const loading = ref(false)
const error = ref('')

const handleSubmit = async () => {
  if (!name.value || targetAmount.value === null) {
    error.value = 'Nome e valor alvo são obrigatórios.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await createGoal({
      name: name.value,
      target_amount: targetAmount.value,
      current_amount: currentAmount.value ?? 0,
      target_date: targetDate.value ? toIsoDateString(targetDate.value) : undefined,
    })
    showModal.value = false
    name.value = ''
    targetAmount.value = null
    currentAmount.value = 0
    targetDate.value = null
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
    <Button
      class="inline-flex shrink-0 items-center gap-2 !rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950"
      @click="showModal = true"
    >
      <Icon icon="mdi:plus" class="h-4 w-4" />
      Nova Meta
    </Button>

    <!-- Modal -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Transition name="slide">
            <div v-if="showModal" class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
              <div class="mb-4 flex items-center justify-between">
                <h3 class="text-lg font-semibold text-sepia-900">Nova Meta Financeira</h3>
                <Button text rounded class="!text-sepia-400 hover:!text-sepia-600" @click="showModal = false">
                  <Icon icon="mdi:close" class="h-5 w-5" />
                </Button>
              </div>

              <div class="space-y-4">
                <div>
                  <label class="mb-1 block text-sm font-medium text-sepia-700">Nome da meta</label>
                  <InputText
                    v-model="name"
                    type="text"
                    placeholder="Ex: Aposentadoria, Viagem..."
                    class="w-full"
                  />
                </div>

                <div>
                  <label class="mb-1 block text-sm font-medium text-sepia-700">Valor alvo (R$)</label>
                  <InputNumber
                    v-model="targetAmount"
                    mode="currency"
                    currency="BRL"
                    locale="pt-BR"
                    placeholder="R$ 100.000,00"
                    class="w-full"
                  />
                </div>

                <div>
                  <label class="mb-1 block text-sm font-medium text-sepia-700">Valor atual (R$)</label>
                  <InputNumber
                    v-model="currentAmount"
                    mode="currency"
                    currency="BRL"
                    locale="pt-BR"
                    placeholder="R$ 0,00"
                    class="w-full"
                  />
                </div>

                <div>
                  <label class="mb-1 block text-sm font-medium text-sepia-700">Data alvo</label>
                  <DatePicker v-model="targetDate" date-format="dd/mm/yy" show-icon icon-display="input" show-button-bar class="w-full" />
                </div>

                <p v-if="error" class="text-sm text-vermelho-600">{{ error }}</p>

                <div class="flex justify-end gap-2">
                  <Button
                    class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950"
                    @click="showModal = false"
                  >
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
