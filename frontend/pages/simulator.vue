<script setup lang="ts">
import Button from 'primevue/button'
import Chart from 'primevue/chart'
import { formatBRL } from '@/composables/useCurrency'
import { formatIsoDate, formatIsoDateTime } from '@/composables/useDateFormat'
import { extractApiError } from '@/composables/useApi'
import { useUiStore } from '@/stores/ui'
import { SCENARIO_LABELS } from '@/composables/useFutureProjection'
import { sourceLabel } from '@/composables/useAiReport'

definePageMeta({
  middleware: 'auth',
})

const uiStore = useUiStore()
const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

const { projection } = useFutureProjection()
const { report, loading, error, generate, remove } = useFutureProjectionReport()

const removing = ref(false)

const onGenerate = async () => {
  await generate()
}

const onRemove = async () => {
  if (!report.value) return
  if (!window.confirm(`Excluir a narração gerada em ${formatIsoDateTime(report.value.created_at)}?`)) return
  removing.value = true
  try {
    await remove()
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao excluir a narração.')
  } finally {
    removing.value = false
  }
}

// Mesma convenção de cores do FinancialFreedomCard no dashboard: conservador em
// âmbar, base em latão (sepia), agressivo em azul — nunca verde, que não faz
// parte da paleta do app.
const SCENARIO_COLORS: Record<string, string> = {
  conservative: '#f59e0b',
  base: '#85652f',
  aggressive: '#235777',
}
const STRESS_COLOR = '#8c3331'

const chartData = computed(() => {
  const data = projection.value
  if (!data) return null

  const labels = ['Hoje', ...data.horizons.map((years) => `${years} anos`)]
  const datasets = data.scenarios.map((series) => ({
    label: SCENARIO_LABELS[series.name] || series.name,
    data: [data.currentNetWorth, ...series.values.map((v) => v.netWorth)],
    borderColor: SCENARIO_COLORS[series.name] || '#85652f',
    backgroundColor: 'transparent',
    tension: 0.3,
  }))
  datasets.push({
    label: 'Estresse (choque de mercado + hiato de renda)',
    data: [data.currentNetWorth, ...data.stress.map((v) => v.netWorth)],
    borderColor: STRESS_COLOR,
    backgroundColor: 'transparent',
    borderDash: [6, 4],
    tension: 0.3,
  })
  return { labels, datasets }
})

const chartOptions = {
  plugins: {
    legend: { position: 'bottom' },
    tooltip: {
      callbacks: {
        label: (ctx: { dataset: { label: string }, parsed: { y: number } }) =>
          `${ctx.dataset.label}: ${formatBRL(ctx.parsed.y)}`,
      },
    },
  },
  scales: {
    y: { ticks: { callback: (value: number) => formatBRL(value) } },
  },
}

const listSections = computed(() => {
  if (!report.value) return []
  return [
    {
      key: 'leverage_explanation',
      title: 'Por que esses ajustes ajudam',
      icon: 'mdi:trending-up',
      accent: 'text-azul-600',
      items: report.value.leverage_explanation,
    },
    {
      key: 'goal_commentary',
      title: 'Comentário sobre as metas',
      icon: 'mdi:flag-outline',
      accent: 'text-sepia-700',
      items: report.value.goal_commentary,
    },
  ].filter((section) => section.items?.length)
})

const isEmpty = computed(
  () => Boolean(report.value) && !report.value?.narrative && listSections.value.length === 0,
)
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Simulador de futuro financeiro</h1>
      <p class="mt-1 text-sepia-600">
        Projeção do seu patrimônio em 5, 10 e 20 anos, em três cenários de retorno, mais um
        cenário de estresse e os ajustes que mais mudariam o resultado.
      </p>
    </div>

    <div v-if="!projection" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:loading" class="mx-auto mb-3 h-8 w-8 animate-spin text-sepia-400" />
      <p class="text-sepia-500">Calculando a projeção...</p>
    </div>

    <template v-else>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Patrimônio atual</p>
          <p :class="['mt-2 font-mono text-2xl font-bold text-sepia-900', blur]">
            {{ formatBRL(projection.currentNetWorth) }}
          </p>
        </article>
        <article class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">
            Aporte mensal médio (últimos 3 meses)
          </p>
          <p :class="['mt-2 font-mono text-2xl font-bold text-azul-700', blur]">
            {{ formatBRL(projection.monthlyContribution) }}
          </p>
        </article>
      </div>

      <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-3 text-base font-semibold text-sepia-900">Cenários de patrimônio projetado</h3>
        <div v-if="chartData" :class="['h-80', blur]">
          <Chart type="line" :data="chartData" :options="chartOptions" class="h-full" />
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-3 flex items-center gap-2 text-base font-semibold text-sepia-900">
            <Icon icon="mdi:lightning-bolt-outline" class="h-5 w-5 text-azul-600" />
            Pontos de alavancagem (impacto em 20 anos)
          </h3>
          <ul v-if="projection.leveragePoints.length" class="space-y-3">
            <li
              v-for="point in projection.leveragePoints"
              :key="point.key"
              class="flex items-center justify-between gap-3 text-sm"
            >
              <span class="text-sepia-700">{{ point.label }}</span>
              <span :class="['shrink-0 font-mono font-medium text-azul-700', blur]">
                {{ point.impact >= 0 ? '+' : '' }}{{ formatBRL(point.impact) }}
              </span>
            </li>
          </ul>
          <p v-else class="text-sm text-sepia-400">
            Sem histórico de renda suficiente para calcular ajustes.
          </p>
        </div>

        <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
          <h3 class="mb-3 flex items-center gap-2 text-base font-semibold text-sepia-900">
            <Icon icon="mdi:flag-checkered" class="h-5 w-5 text-sepia-700" />
            Viabilidade de metas com data-alvo
          </h3>
          <ul v-if="projection.goals.length" class="space-y-3">
            <li v-for="goal in projection.goals" :key="goal.id" class="text-sm">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <p class="font-medium text-sepia-900">{{ goal.name }}</p>
                  <p class="text-xs text-sepia-400">
                    Alvo {{ formatBRL(goal.targetAmount) }} até {{ formatIsoDate(goal.targetDate) }}
                  </p>
                </div>
                <span
                  :class="[
                    'shrink-0 rounded-full px-3 py-1 text-xs font-medium',
                    goal.onTrack ? 'bg-azul-100 text-azul-700' : 'bg-vermelho-100 text-vermelho-700',
                  ]"
                >
                  {{ goal.onTrack ? 'No caminho' : 'Fora do caminho' }}
                </span>
              </div>
              <p v-if="!goal.onTrack" :class="['mt-1 text-xs text-vermelho-600', blur]">
                Falta cobrir {{ formatBRL(goal.shortfall) }} até a data-alvo.
              </p>
            </li>
          </ul>
          <p v-else class="text-sm text-sepia-400">
            Nenhuma meta ativa com data-alvo definida ainda.
          </p>
        </div>
      </div>
    </template>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 class="text-base font-semibold text-sepia-900">Narração por IA</h3>
          <p class="text-xs text-sepia-400">
            {{
              report
                ? `Última narração gerada em ${formatIsoDateTime(report.created_at)}. Reanalisar substitui esta narração -- não fica histórico.`
                : 'Explica os cenários acima em linguagem natural, com um modelo rodando localmente.'
            }}
          </p>
        </div>
        <Button
          :disabled="loading || !projection"
          class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-50 whitespace-nowrap shrink-0"
          @click="onGenerate"
        >
          {{ loading ? 'Narrando...' : (report ? 'Reanalisar' : 'Gerar narração') }}
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
          {{ removing ? 'Excluindo...' : 'Excluir esta narração' }}
        </button>
      </div>

      <p v-if="isEmpty" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center text-sm text-sepia-500">
        O modelo não retornou conteúdo. Tente gerar novamente.
      </p>

      <div v-if="report.narrative" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-3 text-base font-semibold text-sepia-900">O que os cenários significam</h3>
        <p class="whitespace-pre-line text-sm leading-relaxed text-sepia-700">{{ report.narrative }}</p>
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

      <div v-if="report.sources?.length" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">Fontes usadas</h3>
        <p class="mb-3 text-xs text-sepia-400">
          Dados do seu histórico enviados ao modelo, com a relevância de cada um.
        </p>
        <ul class="flex flex-wrap gap-2">
          <li
            v-for="source in report.sources"
            :key="`${source.source_type}-${source.source_id}`"
            class="flex items-center gap-2 rounded-full border border-sepia-200 bg-sepia-50 px-3 py-1 text-xs text-sepia-700"
          >
            <span>{{ sourceLabel(source) }}</span>
            <span class="text-sepia-400">{{ (source.similarity * 100).toFixed(0) }}%</span>
          </li>
        </ul>
        <p v-if="report.index" class="mt-3 text-xs text-sepia-400">
          Índice: {{ report.index.indexed }} atualizados, {{ report.index.skipped }} inalterados,
          {{ report.index.removed }} removidos.
        </p>
      </div>
    </template>

    <div v-else-if="!error" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:robot-outline" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma narração gerada ainda.</p>
      <p class="mt-1 text-sm text-sepia-400">Clique em "Gerar narração" para explicar os cenários acima.</p>
    </div>
  </section>
</template>
