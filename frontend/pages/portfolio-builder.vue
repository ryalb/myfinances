<script setup lang="ts">
import Button from 'primevue/button'
import Chart from 'primevue/chart'
import { formatIsoDateTime } from '@/composables/useDateFormat'
import { extractApiError } from '@/composables/useApi'
import { useUiStore } from '@/stores/ui'
import { ASSET_CLASS_LABELS } from '@/composables/usePortfolioTargets'

definePageMeta({
  middleware: 'auth',
})

const uiStore = useUiStore()
const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const { targets, saveTargets } = usePortfolioTargets()
const { allocation, refresh: refreshAllocation } = useAssetAllocation()
const { createTag } = useFinanceTags('asset_class')
const { report, loading, error, generate, remove } = usePortfolioBuilderReport()

const editorItems = Object.entries(ASSET_CLASS_LABELS).map(([key, label]) => ({ key, label }))
const initialValues = computed(() =>
  Object.fromEntries((targets.value || []).map((t) => [t.asset_class, t.target_percentage])),
)

const savingTargets = ref(false)
const targetsError = ref('')
const onSaveTargets = async (values: Record<string, number>) => {
  savingTargets.value = true
  targetsError.value = ''
  try {
    const rows = Object.entries(values).map(([asset_class, target_percentage]) => ({
      asset_class,
      target_percentage,
    }))
    await saveTargets(rows)
    await refreshAllocation()
  } catch (e: unknown) {
    targetsError.value = extractApiError(e, 'Erro ao salvar os alvos.')
  } finally {
    savingTargets.value = false
  }
}

const chartData = computed(() => {
  const rows = allocation.value?.drift ?? []
  if (!rows.length) return null
  return {
    labels: rows.map((row) => row.label),
    datasets: [
      { label: 'Alvo', data: rows.map((row) => row.targetPercentage), backgroundColor: '#85652f' },
      { label: 'Atual', data: rows.map((row) => row.actualPercentage), backgroundColor: '#235777' },
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

const pendingInvestmentClass = ref<Record<number, string>>({})
const taggingInvestmentId = ref<number | null>(null)
const onTagInvestment = async (investmentId: number) => {
  const value = pendingInvestmentClass.value[investmentId]
  if (!value) return
  taggingInvestmentId.value = investmentId
  try {
    await createTag({ investment: investmentId, value })
    await refreshAllocation()
  } finally {
    taggingInvestmentId.value = null
  }
}

const taggingAccountId = ref<number | null>(null)
const onTagAccount = async (accountId: number) => {
  taggingAccountId.value = accountId
  try {
    await createTag({ account: accountId, value: 'cash_reserve' })
    await refreshAllocation()
  } finally {
    taggingAccountId.value = null
  }
}

const removing = ref(false)
const onGenerate = async () => {
  await generate()
}
const onRemove = async () => {
  if (!report.value) return
  if (!window.confirm(`Excluir a orientação gerada em ${formatIsoDateTime(report.value.created_at)}?`)) return
  removing.value = true
  try {
    await remove()
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao excluir a orientação.')
  } finally {
    removing.value = false
  }
}

const listSections = computed(() => {
  if (!report.value) return []
  return [
    {
      key: 'rebalancing_actions',
      title: 'Ações de rebalanceamento',
      icon: 'mdi:swap-horizontal',
      accent: 'text-azul-600',
      items: report.value.rebalancing_actions,
    },
    {
      key: 'common_mistakes',
      title: 'Erros comuns identificados',
      icon: 'mdi:alert-circle-outline',
      accent: 'text-amber-600',
      items: report.value.common_mistakes,
    },
  ].filter((section) => section.items?.length)
})

const isEmpty = computed(
  () => Boolean(report.value) && !report.value?.guidance && listSections.value.length === 0,
)
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Construtor de portfólio</h1>
      <p class="mt-1 text-sepia-600">
        Defina a alocação-alvo por classe de ativo, compare com o que você realmente tem hoje e
        peça orientação Bogleheads para corrigir o desvio.
      </p>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-4 text-base font-semibold text-sepia-900">Alocação-alvo</h3>
      <AllocationTargetEditor
        :items="editorItems"
        :initial-values="initialValues"
        :saving="savingTargets"
        @save="onSaveTargets"
      />
      <p v-if="targetsError" class="mt-2 text-xs text-vermelho-600">{{ targetsError }}</p>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-4 text-base font-semibold text-sepia-900">Alvo x atual</h3>
      <div v-if="chartData" :class="['h-64', blur]">
        <Chart type="bar" :data="chartData" :options="chartOptions" class="h-full" />
      </div>
      <p v-else class="text-sm text-sepia-400">
        Defina ao menos um alvo e sincronize seus investimentos para ver o comparativo.
      </p>
    </div>

    <div
      v-if="allocation?.untaggedInvestments?.length || allocation?.taggableCashAccounts?.length"
      class="grid gap-4 lg:grid-cols-2"
    >
      <div v-if="allocation?.untaggedInvestments?.length" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">Investimentos sem classe definida</h3>
        <p class="mb-3 text-xs text-sepia-400">
          O tipo destes ativos é ambíguo (fundo, ETF ou COE) -- diga a classe real de cada um.
        </p>
        <ul class="space-y-3">
          <li v-for="investment in allocation.untaggedInvestments" :key="investment.id" class="flex items-center gap-2">
            <span class="flex-1 truncate text-sm text-sepia-700">{{ investment.name }}</span>
            <select
              v-model="pendingInvestmentClass[investment.id]"
              class="rounded-lg border border-sepia-300 px-2 py-1 text-xs focus:border-sepia-500 focus:outline-none"
            >
              <option value="" disabled>Classificar como...</option>
              <option v-for="(label, key) in ASSET_CLASS_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
            <button
              type="button"
              :disabled="!pendingInvestmentClass[investment.id] || taggingInvestmentId === investment.id"
              class="shrink-0 rounded-lg bg-sepia-100 px-3 py-1 text-xs font-medium text-sepia-700 hover:bg-sepia-200 disabled:opacity-40"
              @click="onTagInvestment(investment.id)"
            >
              {{ taggingInvestmentId === investment.id ? '...' : 'Marcar' }}
            </button>
          </li>
        </ul>
      </div>

      <div v-if="allocation?.taggableCashAccounts?.length" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">Contas de reserva de emergência</h3>
        <p class="mb-3 text-xs text-sepia-400">
          Marque qual conta corrente/poupança representa sua reserva -- sem marcar, o saldo não
          entra na alocação (é tratado como dinheiro de gasto).
        </p>
        <ul class="space-y-3">
          <li v-for="acc in allocation.taggableCashAccounts" :key="acc.id" class="flex items-center justify-between gap-2">
            <span class="flex-1 truncate text-sm text-sepia-700">{{ acc.name }}</span>
            <button
              type="button"
              :disabled="taggingAccountId === acc.id"
              class="shrink-0 rounded-lg bg-sepia-100 px-3 py-1 text-xs font-medium text-sepia-700 hover:bg-sepia-200 disabled:opacity-40"
              @click="onTagAccount(acc.id)"
            >
              {{ taggingAccountId === acc.id ? '...' : 'Marcar como reserva' }}
            </button>
          </li>
        </ul>
      </div>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 class="text-base font-semibold text-sepia-900">Orientação por IA</h3>
          <p class="text-xs text-sepia-400">
            {{
              report
                ? `Última orientação gerada em ${formatIsoDateTime(report.created_at)}. Reanalisar substitui esta orientação -- não fica histórico.`
                : 'Recomendações Bogleheads em cima do alvo x atual acima, com um modelo rodando localmente.'
            }}
          </p>
        </div>
        <Button
          :disabled="loading"
          class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-50 whitespace-nowrap"
          @click="onGenerate"
        >
          {{ loading ? 'Analisando...' : (report ? 'Reanalisar' : 'Gerar orientação') }}
        </Button>
      </div>
    </div>

    <p v-if="error" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ error }}
    </p>

    <div v-if="loading" class="rounded-lg border border-sepia-200 bg-white p-8 text-center shadow-sm">
      <Icon icon="mdi:loading" class="mx-auto mb-3 h-8 w-8 animate-spin text-sepia-400" />
      <p class="text-sm text-sepia-500">Consultando o modelo local...</p>
    </div>

    <template v-else-if="report">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <p class="flex-1 rounded-lg border border-sepia-200 bg-sepia-50 px-4 py-3 text-xs text-sepia-600">
          <Icon icon="mdi:information-outline" class="mr-1 inline h-4 w-4 align-text-bottom" />
          {{ report.disclaimer }}
        </p>
        <button
          type="button"
          :disabled="removing"
          class="shrink-0 text-xs text-vermelho-600 hover:underline disabled:opacity-50"
          @click="onRemove"
        >
          {{ removing ? 'Excluindo...' : 'Excluir esta orientação' }}
        </button>
      </div>

      <p v-if="isEmpty" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center text-sm text-sepia-500">
        O modelo não retornou conteúdo. Tente gerar novamente.
      </p>

      <div v-if="report.guidance" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-3 text-base font-semibold text-sepia-900">Estado da carteira</h3>
        <p class="whitespace-pre-line text-sm leading-relaxed text-sepia-700">{{ report.guidance }}</p>
      </div>

      <div v-if="listSections.length" class="grid gap-4 lg:grid-cols-2">
        <div
          v-for="section in listSections"
          :key="section.key"
          class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm"
        >
          <h3 class="mb-3 flex items-center gap-2 text-base font-semibold text-sepia-900">
            <Icon :icon="section.icon" :class="['h-5 w-5', section.accent]" />
            {{ section.title }}
          </h3>
          <ul class="space-y-2">
            <li v-for="(item, idx) in section.items" :key="idx" class="flex gap-2 text-sm text-sepia-700">
              <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sepia-300" />
              <span>{{ item }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>

    <div v-else-if="!error" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:robot-outline" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma orientação gerada ainda.</p>
      <p class="mt-1 text-sm text-sepia-400">Clique em "Gerar orientação" para receber recomendações sobre a alocação acima.</p>
    </div>
  </section>
</template>
