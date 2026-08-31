<script setup lang="ts">
import Button from 'primevue/button'
import { sourceLabel } from '@/composables/useAiReport'
import { formatBRL, formatPercent } from '@/composables/useCurrency'
import { formatIsoDateTime } from '@/composables/useDateFormat'
import { extractApiError } from '@/composables/useApi'

definePageMeta({
  middleware: 'auth',
})

const { report, loading, error, generate, remove } = useExecutiveReport()
const { projection } = useFutureProjection()

// Pré-preenche com a mesma média de poupança que o backend usa como default
// quando o campo fica vazio -- só um palpite inicial, o usuário pode mudar.
const contributionAmount = ref<number | null>(null)
watchEffect(() => {
  if (contributionAmount.value === null && projection.value?.monthlyContribution) {
    contributionAmount.value = Math.round(projection.value.monthlyContribution * 100) / 100
  }
})

const removing = ref(false)

const onGenerate = async () => {
  await generate(contributionAmount.value ?? undefined)
}

const onRemove = async () => {
  if (!report.value) return
  if (!window.confirm(`Excluir o relatório gerado em ${formatIsoDateTime(report.value.created_at)}?`)) return
  removing.value = true
  try {
    await remove()
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao excluir o relatório.')
  } finally {
    removing.value = false
  }
}

const listSections = computed(() => {
  if (!report.value) return []
  return [
    {
      key: 'goal_fit',
      title: 'A carteira faz sentido para meus objetivos?',
      icon: 'mdi:target-arrow',
      accent: 'text-azul-600',
      items: report.value.goal_fit,
    },
    {
      key: 'performance_verdict',
      title: 'O rendimento está bom ou vale mudar de aplicação?',
      icon: 'mdi:chart-line-variant',
      accent: 'text-amber-600',
      items: report.value.performance_verdict,
    },
    {
      key: 'contribution_rationale',
      title: 'Por que este plano de aporte',
      icon: 'mdi:cash-plus',
      accent: 'text-sepia-700',
      items: report.value.contribution_rationale,
    },
  ].filter((section) => section.items?.length)
})

// A LLM pode devolver tudo vazio (modelo pequeno, contexto magro). Sem este aviso
// a tela mostraria cards em branco e pareceria bug.
const isEmpty = computed(
  () => Boolean(report.value) && !report.value?.summary && listSections.value.length === 0,
)
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Relatório executivo</h1>
      <p class="mt-1 text-sepia-600">
        Uma resposta direta: suas aplicações fazem sentido para seus objetivos, o rendimento está
        bom, e quanto aportar em cada classe no próximo aporte -- gerado por um modelo rodando
        localmente.
      </p>
    </div>

    <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
      <label class="mb-1 block text-sm font-medium text-sepia-700">
        Valor do próximo aporte
        <span class="font-normal text-sepia-400">(opcional -- sem informar, usamos sua média de poupança dos últimos 3 meses)</span>
      </label>
      <div class="flex flex-col gap-2 sm:flex-row">
        <input
          v-model.number="contributionAmount"
          type="number"
          min="0"
          step="0.01"
          placeholder="Ex: 1000.00"
          class="w-full rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500"
          @keyup.enter="onGenerate"
        >
        <Button
          :disabled="loading"
          class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-50 whitespace-nowrap shrink-0"
          @click="onGenerate"
        >
          {{ loading ? 'Analisando...' : (report ? 'Reanalisar' : 'Gerar relatório executivo') }}
        </Button>
      </div>
      <p class="mt-2 text-xs text-sepia-400">
        {{
          report
            ? `Último relatório gerado em ${formatIsoDateTime(report.created_at)}. Reanalisar substitui este relatório -- não fica histórico.`
            : 'A primeira geração indexa seus dados e pode levar mais tempo.'
        }}
      </p>
    </div>

    <p v-if="error" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ error }}
    </p>

    <div v-if="loading" class="rounded-lg border border-sepia-200 bg-white p-8 text-center shadow-sm">
      <Icon icon="mdi:loading" class="mx-auto mb-3 h-8 w-8 animate-spin text-sepia-400" />
      <p class="text-sm text-sepia-500">Indexando dados e consultando o modelo local...</p>
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
          {{ removing ? 'Excluindo...' : 'Excluir este relatório' }}
        </button>
      </div>

      <p v-if="isEmpty" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center text-sm text-sepia-500">
        O modelo não retornou conteúdo. Tente gerar novamente.
      </p>

      <div v-if="report.summary" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-3 text-base font-semibold text-sepia-900">Resumo</h3>
        <p class="whitespace-pre-line text-sm leading-relaxed text-sepia-700">{{ report.summary }}</p>
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

      <div v-if="report.contribution_plan?.length" class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-1 text-base font-semibold text-sepia-900">Sugestão de aporte por classe</h3>
        <p class="mb-3 text-xs text-sepia-400">
          Como distribuir {{ formatBRL(report.contribution_amount) }} entre as classes para reduzir
          o desvio da alocação-alvo.
        </p>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-sepia-200 text-left text-xs text-sepia-400">
              <th class="py-2 font-medium">Classe</th>
              <th class="py-2 font-medium">Alvo</th>
              <th class="py-2 font-medium">Atual</th>
              <th class="py-2 text-right font-medium">Sugestão de aporte</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in report.contribution_plan"
              :key="row.asset_class"
              class="border-b border-sepia-100 last:border-0"
            >
              <td class="py-2 text-sepia-700">{{ row.label }}</td>
              <td class="py-2 text-sepia-500">{{ formatPercent(row.target_percentage) }}</td>
              <td class="py-2 text-sepia-500">{{ formatPercent(row.actual_percentage) }}</td>
              <td class="py-2 text-right font-medium text-sepia-900">{{ formatBRL(row.suggested_amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Rastreabilidade: o que o modelo recebeu como contexto -->
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
      <p class="text-sepia-500">Nenhum relatório gerado ainda.</p>
      <p class="mt-1 text-sm text-sepia-400">Clique em "Gerar relatório executivo" para receber a análise acima.</p>
    </div>
  </section>
</template>
