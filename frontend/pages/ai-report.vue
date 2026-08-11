<script setup lang="ts">
import Button from 'primevue/button'
import { sourceLabel } from '@/composables/useAiReport'
import type { PortfolioReport } from '@/composables/useAiReport'
import { formatIsoDateTime } from '@/composables/useDateFormat'

definePageMeta({
  middleware: 'auth',
})

const { report, loading, error, generate, view } = useAiReport()
const query = ref('')

// Histórico dos relatórios já gerados, persistidos no backend para consulta
// posterior -- sem isso um refresh de página perdia a análise.
const {
  items: history,
  count: historyCount,
  refresh: refreshHistory,
} = usePaginatedList<PortfolioReport>('ai-reports', '/ai/portfolio-reports/', { pageSize: 10 })

const onGenerate = async () => {
  await generate(query.value)
  await refreshHistory()
}

// Ao entrar na tela, mostra o relatório mais recente em vez de ficar em branco:
// a análise já existe, só não foi gerada nesta sessão.
watch(
  history,
  (items) => {
    if (!report.value && items.length) view(items[0])
  },
  { immediate: true },
)

const formatDate = formatIsoDateTime

const listSections = computed(() => {
  if (!report.value) return []
  return [
    {
      key: 'strengths',
      title: 'Pontos fortes',
      icon: 'mdi:check-circle-outline',
      accent: 'text-emerald-600',
      items: report.value.strengths,
    },
    {
      key: 'weaknesses',
      title: 'Pontos de atenção',
      icon: 'mdi:alert-circle-outline',
      accent: 'text-amber-600',
      items: report.value.weaknesses,
    },
    {
      key: 'adjustments',
      title: 'Ajustes nas aplicações atuais',
      icon: 'mdi:tune-variant',
      accent: 'text-sepia-700',
      items: report.value.adjustments,
    },
    {
      key: 'suggestions',
      title: 'Novas aplicações sugeridas',
      icon: 'mdi:lightbulb-outline',
      accent: 'text-sepia-700',
      items: report.value.suggestions,
    },
  ].filter((section) => section.items?.length)
})

// A LLM pode devolver tudo vazio (modelo pequeno, contexto magro). Sem este aviso
// a tela mostraria cards em branco e pareceria bug.
const isEmpty = computed(
  () =>
    Boolean(report.value)
    && !report.value?.summary
    && !report.value?.projections
    && listSections.value.length === 0,
)
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Relatório de portfólio com IA</h1>
      <p class="mt-1 text-sepia-600">
        Análise dos seus dados reais, gerada por um modelo rodando localmente.
      </p>
    </div>

    <div class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
      <label class="mb-1 block text-sm font-medium text-sepia-700">
        Foco da análise
        <span class="font-normal text-sepia-400">(opcional)</span>
      </label>
      <div class="flex flex-col gap-2 sm:flex-row">
        <input
          v-model="query"
          type="text"
          placeholder="Ex: onde estou gastando demais? dá para aumentar o aporte?"
          class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          @keyup.enter="onGenerate"
        >
        <Button
          :disabled="loading"
          class="!rounded-lg !bg-sepia-600 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-700 disabled:!opacity-50 whitespace-nowrap"
          @click="onGenerate"
        >
          {{ loading ? 'Analisando...' : 'Gerar relatório' }}
        </Button>
      </div>
      <p class="mt-2 text-xs text-sepia-400">
        A primeira geração indexa seus dados e pode levar mais tempo.
      </p>
    </div>

    <div v-if="history.length" class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
      <h3 class="mb-3 text-sm font-semibold text-sepia-900">Relatórios anteriores</h3>
      <ul class="flex flex-wrap gap-2">
        <li v-for="item in history" :key="item.id">
          <button
            type="button"
            :class="[
              'rounded-full border px-3 py-1 text-xs transition',
              report?.id === item.id
                ? 'border-sepia-600 bg-sepia-600 text-white'
                : 'border-sepia-200 bg-sepia-50 text-sepia-700 hover:border-sepia-400',
            ]"
            @click="view(item)"
          >
            {{ formatDate(item.created_at) }}
          </button>
        </li>
      </ul>
      <p v-if="historyCount > history.length" class="mt-2 text-xs text-sepia-400">
        Mostrando {{ history.length }} de {{ historyCount }} relatórios.
      </p>
    </div>

    <p v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ error }}
    </p>

    <div v-if="loading" class="rounded-xl border border-sepia-200 bg-white p-8 text-center shadow-sm">
      <Icon icon="mdi:loading" class="mx-auto mb-3 h-8 w-8 animate-spin text-sepia-400" />
      <p class="text-sm text-sepia-500">Indexando dados e consultando o modelo local...</p>
    </div>

    <template v-else-if="report">
      <p class="rounded-lg border border-sepia-200 bg-sepia-50 px-4 py-3 text-xs text-sepia-600">
        <Icon icon="mdi:information-outline" class="mr-1 inline h-4 w-4 align-text-bottom" />
        {{ report.disclaimer }}
      </p>

      <p v-if="isEmpty" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center text-sm text-sepia-500">
        O modelo não retornou conteúdo. Tente novamente ou reformule o foco da análise.
      </p>

      <div v-if="report.summary" class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-2 text-lg font-semibold text-sepia-900">Resumo</h3>
        <p class="whitespace-pre-line text-sm leading-relaxed text-sepia-700">{{ report.summary }}</p>
      </div>

      <div v-if="listSections.length" class="grid gap-4 lg:grid-cols-2">
        <div
          v-for="section in listSections"
          :key="section.key"
          class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm"
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

      <div v-if="report.projections" class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-2 flex items-center gap-2 text-base font-semibold text-sepia-900">
          <Icon icon="mdi:chart-line" class="h-5 w-5 text-sepia-700" />
          Projeções
        </h3>
        <p class="whitespace-pre-line text-sm leading-relaxed text-sepia-700">{{ report.projections }}</p>
      </div>

      <!-- Rastreabilidade: o que o modelo recebeu como contexto -->
      <div v-if="report.sources?.length" class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm">
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
      <p class="text-sepia-500">Nenhum relatório gerado ainda.</p>
      <p class="mt-1 text-sm text-sepia-400">Clique em gerar para analisar seu portfólio.</p>
    </div>
  </section>
</template>
