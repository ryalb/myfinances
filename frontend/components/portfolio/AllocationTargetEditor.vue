<script setup lang="ts">
import Button from 'primevue/button'

const props = defineProps<{
  items: { key: string, label: string }[]
  initialValues?: Record<string, number>
  saving?: boolean
}>()

const emit = defineEmits<{ save: [values: Record<string, number>] }>()

const values = ref<Record<string, string>>({})

// Reabastece quando os alvos salvos chegam (ou trocam) -- o editor sempre
// reflete o que está persistido, nunca um estado que sobrevive a um refresh.
watch(
  () => props.initialValues,
  (initial) => {
    values.value = Object.fromEntries(
      props.items.map((item) => [item.key, String(initial?.[item.key] ?? 0)]),
    )
  },
  { immediate: true },
)

const total = computed(() =>
  props.items.reduce((sum, item) => sum + (Number(values.value[item.key]) || 0), 0),
)

// Mesma tolerância de 0.5 p.p. da view (`PortfolioTargetsAPIView.put`): evita
// que arredondamento (33.33 × 3 = 99.99) trave o botão sem motivo real.
const isValid = computed(() => Math.abs(total.value - 100) <= 0.5)

const onSave = () => {
  if (!isValid.value) return
  const parsed = Object.fromEntries(
    props.items.map((item) => [item.key, Number(values.value[item.key]) || 0]),
  )
  emit('save', parsed)
}
</script>

<template>
  <div class="space-y-3">
    <div v-for="item in items" :key="item.key" class="flex items-center gap-3">
      <span class="w-40 shrink-0 text-sm text-sepia-700">{{ item.label }}</span>
      <input
        v-model="values[item.key]"
        type="number"
        min="0"
        max="100"
        step="0.1"
        class="w-24 rounded-lg border border-sepia-300 px-2 py-1 text-right text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
      >
      <span class="text-sm text-sepia-400">%</span>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3 border-t border-sepia-200 pt-3">
      <span :class="['text-sm font-medium', isValid ? 'text-azul-700' : 'text-vermelho-600']">
        Soma: {{ total.toFixed(1) }}%
      </span>
      <Button
        :disabled="!isValid || saving"
        class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-50"
        @click="onSave"
      >
        {{ saving ? 'Salvando...' : 'Salvar alvos' }}
      </Button>
    </div>
    <p v-if="!isValid" class="text-xs text-vermelho-600">
      A soma dos alvos deve ficar perto de 100% para salvar.
    </p>
  </div>
</template>
