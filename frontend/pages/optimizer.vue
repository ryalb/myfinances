<script setup lang="ts">
import Chart from 'primevue/chart'
import { extractApiError } from '@/composables/useApi'
import { useUiStore } from '@/stores/ui'
import { BUDGET_BUCKET_LABELS, TAGGABLE_BUCKETS } from '@/composables/useBudgetBucketTargets'

definePageMeta({
  middleware: 'auth',
})

const uiStore = useUiStore()
const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const { targets, saveTargets } = useBudgetBucketTargets()
const { optimizer, refresh: refreshOptimizer } = useBudgetBucketDrift()
const { tags: bucketTags, createTag, updateTag, deleteTag } = useFinanceTags('budget_bucket')

const editorItems = Object.entries(BUDGET_BUCKET_LABELS).map(([key, label]) => ({ key, label }))
const initialValues = computed(() =>
  Object.fromEntries((targets.value || []).map((t) => [t.bucket, t.target_percentage])),
)

const savingTargets = ref(false)
const targetsError = ref('')
const onSaveTargets = async (values: Record<string, number>) => {
  savingTargets.value = true
  targetsError.value = ''
  try {
    const rows = Object.entries(values).map(([bucket, target_percentage]) => ({
      bucket,
      target_percentage,
    }))
    await saveTargets(rows)
    await refreshOptimizer()
  } catch (e: unknown) {
    targetsError.value = extractApiError(e, 'Erro ao salvar os alvos.')
  } finally {
    savingTargets.value = false
  }
}

const chartData = computed(() => {
  const rows = optimizer.value?.drift ?? []
  if (!rows.length) return null
  return {
    labels: rows.map((row) => row.label),
    datasets: [
      { label: 'Alvo', data: rows.map((row) => row.targetPercentage), backgroundColor: '#85652f' },
      { label: 'Realizado', data: rows.map((row) => row.actualPercentage), backgroundColor: '#235777' },
    ],
  }
})
const chartOptions = {
  indexAxis: 'y' as const,
  plugins: {
    legend: { position: 'bottom' as const },
    tooltip: {
      callbacks: {
        label: (ctx: { dataset: { label: string }, parsed: { x: number } }) =>
          `${ctx.dataset.label}: ${ctx.parsed.x.toFixed(1)}%`,
      },
    },
  },
  scales: { x: { ticks: { callback: (value: number) => `${value}%` } } },
}

// Pre-preenche o seletor de cada conta com o bucket ja tagueado (se houver);
// trocar de mes/refresh do backend reabastece a partir do que esta salvo.
const accountBucket = ref<Record<number, string>>({})
watch(
  bucketTags,
  (tags) => {
    const map: Record<number, string> = {}
    for (const tag of tags || []) {
      if (tag.account !== null) map[tag.account] = tag.value
    }
    accountBucket.value = map
  },
  { immediate: true },
)

const savingAccountId = ref<number | null>(null)
const accountError = ref('')
const onAccountBucketChange = async (accountId: number) => {
  const value = accountBucket.value[accountId] || ''
  const existing = (bucketTags.value || []).find((tag) => tag.account === accountId)
  savingAccountId.value = accountId
  accountError.value = ''
  try {
    if (!value && existing) {
      await deleteTag(existing.id)
    } else if (value && existing) {
      await updateTag(existing.id, value)
    } else if (value && !existing) {
      await createTag({ account: accountId, value })
    }
    await refreshOptimizer()
  } catch (e: unknown) {
    accountError.value = extractApiError(e, 'Erro ao marcar a conta.')
  } finally {
    savingAccountId.value = null
  }
}
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Otimizador automático</h1>
      <p class="mt-1 text-sepia-600">
        Defina quanto da sua renda mensal deveria ir para cada bucket e acompanhe o realizado --
        só orientação e alertas, nenhuma transferência é feita pelo app.
      </p>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-4 text-base font-semibold text-sepia-900">Alvo por bucket (% da renda)</h3>
      <AllocationTargetEditor
        :items="editorItems"
        :initial-values="initialValues"
        :saving="savingTargets"
        @save="onSaveTargets"
      />
      <p v-if="targetsError" class="mt-2 text-xs text-vermelho-600">{{ targetsError }}</p>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-4 text-base font-semibold text-sepia-900">Alvo x realizado este mês</h3>
      <div v-if="chartData" :class="['h-64', blur]">
        <Chart type="bar" :data="chartData" :options="chartOptions" class="h-full" />
      </div>
      <p v-else class="text-sm text-sepia-400">
        Defina ao menos um alvo e tenha renda registrada no mês para ver o comparativo.
      </p>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-1 text-base font-semibold text-sepia-900">Contas por bucket</h3>
      <p class="mb-3 text-xs text-sepia-400">
        Marque qual bucket cada conta representa -- crédito recebido nela durante o mês conta
        como aporte para aquele bucket. Despesas fixas e discricionário são calculados pela
        categoria dos seus gastos, não precisam de conta marcada.
      </p>
      <ul v-if="optimizer?.accounts?.length" class="space-y-3">
        <li v-for="acc in optimizer.accounts" :key="acc.id" class="flex items-center gap-2">
          <span class="flex-1 truncate text-sm text-sepia-700">{{ acc.name }}</span>
          <select
            v-model="accountBucket[acc.id]"
            :disabled="savingAccountId === acc.id"
            class="rounded-lg border border-sepia-300 px-2 py-1 text-xs focus:border-sepia-500 focus:outline-none disabled:opacity-50"
            @change="onAccountBucketChange(acc.id)"
          >
            <option value="">Nenhum</option>
            <option v-for="bucket in TAGGABLE_BUCKETS" :key="bucket" :value="bucket">
              {{ BUDGET_BUCKET_LABELS[bucket] }}
            </option>
          </select>
        </li>
      </ul>
      <p v-else class="text-sm text-sepia-400">Nenhuma conta sincronizada ainda.</p>
      <p v-if="accountError" class="mt-2 text-xs text-vermelho-600">{{ accountError }}</p>
    </div>
  </section>
</template>
