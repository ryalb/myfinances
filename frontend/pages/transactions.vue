<script setup lang="ts">
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import { extractApiError } from '@/composables/useApi'
import { formatIsoDateOnly, toIsoDateString } from '@/composables/useDateFormat'

definePageMeta({
  middleware: 'auth',
})

type TransactionRow = {
  id: number
  description: string
  amount: number
  type: string
  category: string
  category_is_manual: boolean
  is_internal_transfer: boolean
  booked_at: string
  account_name: string
  institution_name: string
}

const FILTERS_STORAGE_KEY = 'transactions-filters'

const filters = reactive({
  search: '',
  category: '',
  type: '',
  start_date: '',
  end_date: '',
  min_amount: '',
  max_amount: '',
})

if (typeof window !== 'undefined') {
  const saved = localStorage.getItem(FILTERS_STORAGE_KEY)
  if (saved) {
    try {
      const parsed = JSON.parse(saved) as Partial<typeof filters>
      for (const key of Object.keys(filters) as Array<keyof typeof filters>) {
        if (parsed[key] !== undefined) filters[key] = parsed[key] as string
      }
    } catch {
      // Formato antigo ou corrompido: ignora e segue com os padrões.
    }
  }
}

watch(filters, (value) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(value))
  }
})

// A busca é debounced: cada tecla dispararia uma requisição, e o backend faz
// `icontains` sobre o histórico inteiro.
const debouncedSearch = ref(filters.search)
let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => filters.search,
  (value) => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      debouncedSearch.value = value
    }, 300)
  },
)
onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

// Atalhos de período: preenchem `start_date`/`end_date` a partir de um preset em
// vez de forçar o usuário a calcular datas manualmente. `end` é sempre o primeiro
// dia do mês seguinte ao último incluído -- mesmo limite exclusivo que o backend
// usa (`booked_at__lt`), então o mês corrente entra inteiro, dias futuros inclusive
// (parcelas futuras já aparecem na tabela com o selo "Previsto").
const parseIsoDate = (value: string): Date | null => {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

const firstDayOfMonth = (monthsFromNow: number) => {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth() + monthsFromNow, 1)
}

// Um único mês-calendário específico (mês atual = offset 0, "1 mês atrás" = offset -1...).
const singleMonthRange = (monthsAgo: number) => ({
  start: toIsoDateString(firstDayOfMonth(-monthsAgo)),
  end: toIsoDateString(firstDayOfMonth(-monthsAgo + 1)),
})

// Janela corrida terminando no mês corrente (ex.: "últimos 12 meses" inclui o mês atual + 11 anteriores).
const rollingMonthsRange = (months: number) => ({
  start: toIsoDateString(firstDayOfMonth(-months + 1)),
  end: toIsoDateString(firstDayOfMonth(1)),
})

const PERIOD_PRESETS: { key: string, label: string, range: () => { start: string, end: string } | null }[] = [
  { key: 'all', label: 'Todos os períodos', range: () => null },
  { key: 'current-month', label: 'Mês atual', range: () => singleMonthRange(0) },
  { key: '1-month-ago', label: '1 mês atrás', range: () => singleMonthRange(1) },
  { key: '2-months-ago', label: '2 meses atrás', range: () => singleMonthRange(2) },
  { key: '3-months-ago', label: '3 meses atrás', range: () => singleMonthRange(3) },
  { key: 'last-6-months', label: 'Últimos 6 meses', range: () => rollingMonthsRange(6) },
  { key: 'last-12-months', label: 'Último ano', range: () => rollingMonthsRange(12) },
]

// Getter/setter em vez de um `ref` próprio: a fonte da verdade continua sendo
// `start_date`/`end_date` (o que já é filtrado, persistido e exportado). Editar
// "De"/"Até" à mão faz o preset cair para "Personalizado" sozinho, sem precisar
// de uma flag extra pra saber quem mudou o quê.
const periodPreset = computed<string>({
  get() {
    if (!filters.start_date && !filters.end_date) return 'all'
    const match = PERIOD_PRESETS.find((preset) => {
      const range = preset.range()
      return range !== null && range.start === filters.start_date && range.end === filters.end_date
    })
    return match?.key ?? 'custom'
  },
  set(key) {
    const preset = PERIOD_PRESETS.find((item) => item.key === key)
    if (!preset) return
    const range = preset.range()
    filters.start_date = range?.start ?? ''
    filters.end_date = range?.end ?? ''
  },
})

const periodOptions = computed(() => [
  ...PERIOD_PRESETS.map((preset) => ({ label: preset.label, value: preset.key, disabled: false })),
  { label: 'Personalizado', value: 'custom', disabled: true },
])

// O DatePicker e o InputNumber do PrimeVue trabalham com `Date`/`number`, não
// com as strings que `filters` guarda (formato exigido pelo backend, pela
// localStorage e pela lógica de preset acima) -- essas pontes convertem só na
// borda do campo, sem espalhar `Date`/`number` pelo resto da tela.
const startDateModel = computed<Date | null>({
  get: () => parseIsoDate(filters.start_date),
  set: (value) => { filters.start_date = value ? toIsoDateString(value) : '' },
})
const endDateModel = computed<Date | null>({
  get: () => parseIsoDate(filters.end_date),
  set: (value) => { filters.end_date = value ? toIsoDateString(value) : '' },
})

const minAmountModel = computed<number | null>({
  get: () => (filters.min_amount === '' ? null : Number(filters.min_amount)),
  set: (value) => { filters.min_amount = value === null ? '' : String(value) },
})
const maxAmountModel = computed<number | null>({
  get: () => (filters.max_amount === '' ? null : Number(filters.max_amount)),
  set: (value) => { filters.max_amount = value === null ? '' : String(value) },
})

const activeParams = () => ({
  search: debouncedSearch.value,
  category: filters.category,
  type: filters.type,
  start_date: filters.start_date,
  end_date: filters.end_date,
  min_amount: filters.min_amount,
  max_amount: filters.max_amount,
})

// Paginação real: antes o endpoint devolvia o histórico inteiro e a tela cortava
// as 100 primeiras no cliente — o resto viajava pela rede só para ser descartado.
const {
  items: transactions,
  count,
  page,
  totalPages,
  hasNext,
  hasPrevious,
  loading,
  next,
  previous,
  refresh: refreshTransactions,
} = usePaginatedList<TransactionRow>('transactions-page', '/transactions/', {
  pageSize: 50,
  params: activeParams,
})

const { get, post, download, patch, del } = useApi()

// Estatísticas e totais por categoria dos MESMOS filtros da listagem -- os
// cards e gráficos precisam bater com o que está na tabela, não com o
// histórico inteiro.
const { stats, refresh: refreshStats } = useTransactionStats(activeParams)

const statCards = computed(() => [
  { label: 'Receitas', value: formatBRL(stats.value.total_income), tone: 'azul' as const },
  { label: 'Despesas', value: formatBRL(stats.value.total_expenses), tone: 'vermelho' as const },
  {
    label: 'Saldo',
    value: formatBRL(stats.value.balance),
    tone: (stats.value.balance >= 0 ? 'azul' : 'vermelho') as const,
  },
  {
    label: 'Ticket médio',
    value: formatBRL(stats.value.average_expense),
    sublabel: 'Média por despesa',
    tone: 'neutral' as const,
  },
  { label: 'Lançamentos', value: String(stats.value.transaction_count), tone: 'neutral' as const },
])

// Categorias vêm dos dados, não de um enum: podem chegar da Pluggy, de uma regra do
// usuário ou das palavras-chave.
const { data: categories, refresh: refreshCategories } = await useAsyncData(
  'transaction-categories',
  async () => (await get<string[]>('/transactions/categories/')) || [],
  { default: () => [] },
)

const categoryOptions = computed(() => [
  { label: 'Todas', value: '' },
  ...categories.value.map((category) => ({ label: category, value: category })),
])

const TYPE_OPTIONS = [
  { label: 'Todos', value: '' },
  { label: 'Receita', value: 'credit' },
  { label: 'Despesa', value: 'debit' },
]

// A categoria fica sempre editável na tabela (sem clique pra entrar em modo de
// edição): `Select` com `filter` mostra as categorias já existentes com busca
// embutida, e selecionar uma opção salva na hora -- sem clique extra num botão
// "Salvar". Depois de salvar/restaurar, estatísticas e a lista de categorias
// do filtro são recarregadas -- editar pode mudar os totais por categoria.
const savingCategoryIds = ref<Set<number>>(new Set())
const categoryErrors = ref<Map<number, string>>(new Map())

const saveCategory = async (tx: TransactionRow, value: string) => {
  if (!value || value === tx.category) return
  savingCategoryIds.value.add(tx.id)
  categoryErrors.value.delete(tx.id)
  try {
    const updated = await patch<TransactionRow>(`/transactions/${tx.id}/category/`, { category: value })
    if (updated) {
      tx.category = updated.category
      tx.category_is_manual = updated.category_is_manual
    }
    await Promise.all([refreshCategories(), refreshStats()])
  } catch (e: unknown) {
    categoryErrors.value.set(tx.id, extractApiError(e, 'Erro ao salvar a categoria.'))
  } finally {
    savingCategoryIds.value.delete(tx.id)
  }
}

// Apaga a escolha manual e volta para a categoria automática (regras + Pluggy).
const resetCategory = async (tx: TransactionRow) => {
  savingCategoryIds.value.add(tx.id)
  categoryErrors.value.delete(tx.id)
  try {
    const updated = await del<TransactionRow>(`/transactions/${tx.id}/category/`)
    if (updated) {
      tx.category = updated.category
      tx.category_is_manual = updated.category_is_manual
    }
    await Promise.all([refreshCategories(), refreshStats()])
  } catch (e: unknown) {
    categoryErrors.value.set(tx.id, extractApiError(e, 'Erro ao restaurar a categoria automática.'))
  } finally {
    savingCategoryIds.value.delete(tx.id)
  }
}

const hasActiveFilter = computed(() =>
  Object.values(activeParams()).some((value) => value !== ''),
)

const clearFilters = () => {
  filters.search = ''
  filters.category = ''
  filters.type = ''
  filters.start_date = ''
  filters.end_date = ''
  filters.min_amount = ''
  filters.max_amount = ''
  debouncedSearch.value = ''
}

const uiStore = useUiStore()
const blur = computed(() => (uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''))

// Colunas visíveis na tabela -- preferência de exibição, não um filtro (não
// muda o que é buscado, só o que é desenhado), por isso persiste numa chave
// própria em vez de entrar em `filters`.
const TABLE_COLUMNS = [
  { key: 'date', label: 'Data' },
  { key: 'description', label: 'Descrição' },
  { key: 'account', label: 'Conta' },
  { key: 'institution', label: 'Banco' },
  { key: 'category', label: 'Categoria' },
  { key: 'type', label: 'Tipo' },
  { key: 'amount', label: 'Valor' },
] as const

type ColumnKey = typeof TABLE_COLUMNS[number]['key']

const COLUMNS_STORAGE_KEY = 'transactions-hidden-columns'

const hiddenColumns = reactive<Record<ColumnKey, boolean>>({
  date: false,
  description: false,
  account: false,
  institution: false,
  category: false,
  type: false,
  amount: false,
})

if (typeof window !== 'undefined') {
  const savedColumns = localStorage.getItem(COLUMNS_STORAGE_KEY)
  if (savedColumns) {
    try {
      const parsed = JSON.parse(savedColumns) as Partial<Record<ColumnKey, boolean>>
      for (const key of Object.keys(hiddenColumns) as ColumnKey[]) {
        if (parsed[key] !== undefined) hiddenColumns[key] = Boolean(parsed[key])
      }
    } catch {
      // Formato antigo ou corrompido: ignora e segue com tudo visível.
    }
  }
}

watch(hiddenColumns, (value) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(value))
  }
})

const isColumnVisible = (key: ColumnKey) => !hiddenColumns[key]
const toggleColumn = (key: ColumnKey) => {
  hiddenColumns[key] = !hiddenColumns[key]
}

const columnsMenuOpen = ref(false)
const columnsMenuRef = ref<HTMLElement | null>(null)

// Fecha ao clicar fora -- sem lib de popover no projeto, um listener manual no
// documento resolve. O botão que abre o menu fica dentro do próprio `ref`,
// então cliques nele não disparam o fechamento por engano.
const onDocumentClick = (event: MouseEvent) => {
  if (columnsMenuOpen.value && columnsMenuRef.value && !columnsMenuRef.value.contains(event.target as Node)) {
    columnsMenuOpen.value = false
  }
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))

const exporting = ref(false)
const exportError = ref('')

const exportCsv = async () => {
  exporting.value = true
  exportError.value = ''
  try {
    // Os mesmos filtros da tela: um CSV que não corresponde ao que está visível
    // seria pior que não ter exportação.
    const query = new URLSearchParams(
      Object.entries(activeParams()).filter(([, value]) => value !== ''),
    ).toString()
    const today = new Date().toISOString().slice(0, 10)
    await download(
      `/export/transactions.csv${query ? `?${query}` : ''}`,
      `transacoes-${today}.csv`,
    )
  } catch (e: unknown) {
    exportError.value = extractApiError(e, 'Erro ao exportar as transações.')
  } finally {
    exporting.value = false
  }
}

const typeBadge = (tx: TransactionRow) => {
  if (tx.is_internal_transfer) return 'bg-sepia-100 text-sepia-500'
  return tx.type === 'credit' ? 'bg-azul-100 text-azul-700' : 'bg-vermelho-100 text-vermelho-700'
}

// Sincroniza todas as conexões de uma vez em vez de mandar o usuário pra tela
// de integrações e clicar conexão por conexão. Cada POST só enfileira o job no
// Celery; o fim de fato chega pelo WebSocket (`sync_event`, já conectado
// globalmente em `layouts/default.vue`) -- por isso o timeout de segurança,
// igual ao de `ConnectionItem.vue`: sem ele, um evento perdido travaria o
// botão girando pra sempre.
type ConnectionSummary = { id: number, status: string }
const syncingAll = ref(false)
const syncAllError = ref('')
const pendingSyncConnectionIds = ref<Set<number>>(new Set())
const lastSyncEvent = useSyncEvent()
let syncAllTimeout: ReturnType<typeof setTimeout> | null = null

const finishSyncAll = async () => {
  if (syncAllTimeout) {
    clearTimeout(syncAllTimeout)
    syncAllTimeout = null
  }
  syncingAll.value = false
  pendingSyncConnectionIds.value = new Set()
  await Promise.all([refreshTransactions(), refreshStats(), refreshCategories()])
}

watch(lastSyncEvent, (event) => {
  if (!event || !pendingSyncConnectionIds.value.has(event.connectionId)) return
  if (event.status !== 'SUCCESS' && event.status !== 'FAILED') return
  pendingSyncConnectionIds.value.delete(event.connectionId)
  if (pendingSyncConnectionIds.value.size === 0) finishSyncAll()
})

const syncAllConnections = async () => {
  syncingAll.value = true
  syncAllError.value = ''
  try {
    const connections = (await get<ConnectionSummary[]>('/connections/')) ?? []
    const active = connections.filter((conn) => conn.status !== 'expired')
    if (!active.length) {
      syncingAll.value = false
      return
    }
    pendingSyncConnectionIds.value = new Set(active.map((conn) => conn.id))
    await Promise.all(
      active.map((conn) => post(`/connections/${conn.id}/sync/`, { kind: 'incremental' })),
    )
    syncAllTimeout = setTimeout(finishSyncAll, 60_000)
  } catch (e: unknown) {
    syncingAll.value = false
    syncAllError.value = extractApiError(e, 'Erro ao sincronizar as contas.')
  }
}

onUnmounted(() => {
  if (syncAllTimeout) clearTimeout(syncAllTimeout)
})

// Pagamento de fatura de cartao e transferencia entre contas proprias nao sao
// receita nem despesa, so dinheiro mudando de bolso -- rotulo neutro em vez do
// "Receita" que o `type` cru (CREDIT no lado do cartao) sugeriria.
const typeLabel = (tx: TransactionRow) => {
  if (tx.is_internal_transfer) return 'Transferência'
  return tx.type === 'credit' ? 'Receita' : 'Despesa'
}

// Parcelas futuras de compras no cartão (ex: "Amazon 4/4") já entram lançadas com
// booked_at à frente — sem isso elas se misturam ao extrato como se já tivessem ocorrido.
const isFutureTx = (bookedAt: string) => {
  const txDate = new Date(bookedAt)
  txDate.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return txDate > today
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-semibold">Transações</h1>
      <div class="flex items-center gap-3">
        <span class="text-sm text-sepia-500">
          {{ count }} {{ count === 1 ? 'lançamento' : 'lançamentos' }}
          <span v-if="hasActiveFilter" class="text-sepia-400">(filtrado)</span>
        </span>
        <Button
          :disabled="syncingAll"
          class="!inline-flex !shrink-0 !items-center !gap-2 !whitespace-nowrap !rounded-lg !border !border-sepia-300 !bg-white !px-3 !py-1.5 !text-xs !font-medium !text-sepia-700 hover:!bg-sepia-50 disabled:!opacity-40"
          @click="syncAllConnections"
        >
          <Icon :icon="syncingAll ? 'mdi:loading' : 'mdi:refresh'" :class="['h-4 w-4', syncingAll ? 'animate-spin' : '']" />
          {{ syncingAll ? 'Atualizando...' : 'Atualizar contas' }}
        </Button>
        <div ref="columnsMenuRef" class="relative">
          <Button
            class="!inline-flex !shrink-0 !items-center !gap-2 !whitespace-nowrap !rounded-lg !border !border-sepia-300 !bg-white !px-3 !py-1.5 !text-xs !font-medium !text-sepia-700 hover:!bg-sepia-50"
            @click="columnsMenuOpen = !columnsMenuOpen"
          >
            <Icon icon="mdi:view-column-outline" class="h-4 w-4" />
            Colunas
          </Button>
          <div
            v-if="columnsMenuOpen"
            class="absolute right-0 z-10 mt-2 w-48 rounded-lg border border-sepia-200 bg-white p-2 shadow-md"
          >
            <label
              v-for="column in TABLE_COLUMNS" :key="column.key"
              class="flex items-center gap-2 rounded px-2 py-1.5 text-sm text-sepia-700 hover:bg-sepia-50"
            >
              <Checkbox :model-value="isColumnVisible(column.key)" binary @update:model-value="toggleColumn(column.key)" />
              {{ column.label }}
            </label>
          </div>
        </div>
        <Button
          :disabled="exporting || !count"
          class="!inline-flex !shrink-0 !items-center !gap-2 !whitespace-nowrap !rounded-lg !bg-sepia-900 !px-3 !py-1.5 !text-xs !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-40"
          @click="exportCsv"
        >
          <Icon icon="mdi:download-outline" class="h-4 w-4" />
          {{ exporting ? 'Exportando...' : 'Exportar CSV' }}
        </Button>
      </div>
    </div>

    <p v-if="exportError" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ exportError }}
    </p>

    <p v-if="syncAllError" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ syncAllError }}
    </p>

    <!-- Filtros -->
    <div class="rounded-lg border border-sepia-200 bg-white p-4 shadow-sm">
      <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div class="lg:col-span-2">
          <label class="mb-1 block text-xs font-medium text-sepia-700">Buscar na descrição</label>
          <IconField>
            <InputIcon>
              <Icon icon="mdi:magnify" class="h-4 w-4" />
            </InputIcon>
            <InputText v-model="filters.search" type="search" placeholder="Ex: uber, mercado, salário" class="w-full" />
          </IconField>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Categoria</label>
          <Select v-model="filters.category" :options="categoryOptions" option-label="label" option-value="value" class="w-full" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Tipo</label>
          <Select v-model="filters.type" :options="TYPE_OPTIONS" option-label="label" option-value="value" class="w-full" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Período</label>
          <Select
            v-model="periodPreset"
            :options="periodOptions"
            option-label="label"
            option-value="value"
            option-disabled="disabled"
            class="w-full"
          />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">De</label>
          <DatePicker v-model="startDateModel" date-format="dd/mm/yy" show-icon icon-display="input" show-button-bar class="w-full" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Até</label>
          <DatePicker v-model="endDateModel" date-format="dd/mm/yy" show-icon icon-display="input" show-button-bar class="w-full" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Valor mínimo</label>
          <InputNumber v-model="minAmountModel" mode="currency" currency="BRL" locale="pt-BR" :min="0" placeholder="R$ 0,00" class="w-full" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Valor máximo</label>
          <InputNumber v-model="maxAmountModel" mode="currency" currency="BRL" locale="pt-BR" placeholder="Sem limite" class="w-full" />
        </div>
      </div>

      <div class="mt-3 flex justify-end">
        <Button
          :disabled="!hasActiveFilter"
          class="!inline-flex !items-center !gap-1.5 !whitespace-nowrap !rounded-lg !bg-sepia-900 !px-3 !py-1.5 !text-xs !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-40"
          @click="clearFilters"
        >
          <Icon icon="mdi:filter-remove-outline" class="h-4 w-4" />
          Limpar filtros
        </Button>
      </div>
    </div>

    <!-- Estatísticas do período filtrado -->
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      <dashboard-metric-card v-for="card in statCards" :key="card.label" v-bind="card" />
    </div>

    <!-- Totalização por categoria -->
    <div class="grid gap-4 lg:grid-cols-2">
      <transactions-category-totals-chart
        title="Despesas por categoria"
        :items="stats.expense_categories"
        empty-message="Sem despesas para estes filtros."
      />
      <transactions-category-totals-chart
        v-if="stats.income_categories.length"
        title="Receitas por categoria"
        :items="stats.income_categories"
      />
    </div>

    <div v-if="!transactions.length && !loading" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:receipt-outline" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">
        {{ hasActiveFilter ? 'Nenhuma transação para esses filtros.' : 'Nenhuma transação encontrada.' }}
      </p>
      <p class="mt-1 text-sm text-sepia-400">
        {{ hasActiveFilter ? 'Ajuste ou limpe os filtros.' : 'Sincronize suas contas para ver as transações.' }}
      </p>
    </div>

    <div v-else class="overflow-hidden rounded-lg border border-sepia-200 bg-white shadow-sm">
      <DataTable
        :value="transactions"
        data-key="id"
        class="text-sm"
        table-style="width: 100%"
        :row-class="(tx) => ['border-b border-sepia-100 last:border-0', (isFutureTx(tx.booked_at) || tx.is_internal_transfer) ? 'opacity-60' : '']"
        :pt="{ headerRow: { class: 'border-b border-sepia-200 bg-sepia-50' } }"
      >
        <Column v-if="isColumnVisible('date')" header="Data" header-class="px-4 py-3 text-left font-medium text-sepia-600" body-class="whitespace-nowrap px-4 py-3 text-sepia-500">
          <template #body="{ data }">
            {{ formatIsoDateOnly(data.booked_at) }}
            <span v-if="isFutureTx(data.booked_at)" class="ml-1.5 inline-block whitespace-nowrap rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
              Previsto
            </span>
          </template>
        </Column>
        <Column v-if="isColumnVisible('description')" field="description" header="Descrição" header-class="px-4 py-3 text-left font-medium text-sepia-600" body-class="px-4 py-3 font-medium text-sepia-900" />
        <Column v-if="isColumnVisible('account')" header="Conta" header-class="px-4 py-3 text-left font-medium text-sepia-600" body-class="px-4 py-3 text-sepia-600">
          <template #body="{ data }">{{ data.account_name || '—' }}</template>
        </Column>
        <Column v-if="isColumnVisible('institution')" header="Banco" header-class="px-4 py-3 text-left font-medium text-sepia-600" body-class="px-4 py-3 text-sepia-600">
          <template #body="{ data }">{{ data.institution_name || '—' }}</template>
        </Column>
        <Column v-if="isColumnVisible('category')" header="Categoria" header-style="width: 14rem" header-class="px-4 py-3 text-left font-medium text-sepia-600" body-class="px-4 py-3">
          <template #body="{ data }">
            <div class="group flex items-center gap-1">
              <Select
                :model-value="data.category"
                :options="categories"
                filter
                filter-placeholder="Buscar categoria..."
                :disabled="savingCategoryIds.has(data.id)"
                class="w-full"
                @update:model-value="saveCategory(data, $event)"
              />
              <Icon v-if="data.category_is_manual" icon="mdi:pencil" class="h-3 w-3 shrink-0 text-sepia-400" title="Categoria definida manualmente" />
              <Button
                v-if="data.category_is_manual"
                text
                rounded
                size="small"
                :disabled="savingCategoryIds.has(data.id)"
                class="shrink-0 !text-sepia-300 opacity-0 hover:!text-sepia-500 group-hover:opacity-100"
                title="Restaurar categoria automática"
                @click="resetCategory(data)"
              >
                <Icon icon="mdi:restore" class="h-3.5 w-3.5" />
              </Button>
            </div>
            <p v-if="categoryErrors.get(data.id)" class="mt-1 text-[10px] leading-tight text-vermelho-600">{{ categoryErrors.get(data.id) }}</p>
          </template>
        </Column>
        <Column v-if="isColumnVisible('type')" header="Tipo" header-class="px-4 py-3 text-left font-medium text-sepia-600" body-class="px-4 py-3">
          <template #body="{ data }">
            <span :class="['inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', typeBadge(data)]">
              {{ typeLabel(data) }}
            </span>
          </template>
        </Column>
        <Column v-if="isColumnVisible('amount')" header="Valor" header-class="px-4 py-3 text-right font-medium text-sepia-600" body-class="whitespace-nowrap px-4 py-3 text-right font-mono font-medium">
          <template #body="{ data }">
            <span :class="[data.is_internal_transfer ? 'text-sepia-500' : (data.type === 'credit' ? 'text-azul-600' : 'text-vermelho-600'), blur]">
              {{ data.is_internal_transfer ? '' : (data.type === 'credit' ? '+' : '-') }}{{ formatBRL(Math.abs(Number(data.amount))) }}
            </span>
          </template>
        </Column>
      </DataTable>

      <div v-if="totalPages > 1" class="flex items-center justify-between border-t border-sepia-200 px-4 py-3">
        <Button
          :disabled="!hasPrevious || loading"
          class="!whitespace-nowrap !rounded-lg !bg-sepia-900 !px-3 !py-1.5 !text-xs !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-40"
          @click="previous"
        >
          Anterior
        </Button>
        <span class="text-xs text-sepia-500">Página {{ page }} de {{ totalPages }}</span>
        <Button
          :disabled="!hasNext || loading"
          class="!whitespace-nowrap !rounded-lg !bg-sepia-900 !px-3 !py-1.5 !text-xs !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-40"
          @click="next"
        >
          Próxima
        </Button>
      </div>
    </div>
  </section>
</template>
