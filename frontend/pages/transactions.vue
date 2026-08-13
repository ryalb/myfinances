<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'
import { extractApiError } from '@/composables/useApi'
import { formatIsoDateOnly } from '@/composables/useDateFormat'

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
const isoDate = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

const firstDayOfMonth = (monthsFromNow: number) => {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth() + monthsFromNow, 1)
}

// Um único mês-calendário específico (mês atual = offset 0, "1 mês atrás" = offset -1...).
const singleMonthRange = (monthsAgo: number) => ({
  start: isoDate(firstDayOfMonth(-monthsAgo)),
  end: isoDate(firstDayOfMonth(-monthsAgo + 1)),
})

// Janela corrida terminando no mês corrente (ex.: "últimos 12 meses" inclui o mês atual + 11 anteriores).
const rollingMonthsRange = (months: number) => ({
  start: isoDate(firstDayOfMonth(-months + 1)),
  end: isoDate(firstDayOfMonth(1)),
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
} = usePaginatedList<TransactionRow>('transactions-page', '/transactions/', {
  pageSize: 50,
  params: activeParams,
})

const { get, download, patch, del } = useApi()

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

// Edição manual da categoria: um lançamento por vez (`editingCategoryId`), com
// autocomplete pelas categorias já existentes. Depois de salvar/restaurar,
// estatísticas e a lista de categorias do filtro são recarregadas -- editar
// pode introduzir uma categoria nova ou mudar os totais por categoria.
const editingCategoryId = ref<number | null>(null)
const editingCategoryValue = ref('')
// Ref de função, não `ref="..."` direto: o input mora dentro de um `v-for`, e
// uma string-ref ali é coletada num array pelo Vue mesmo com o `v-if` só
// deixando um existir por vez -- `.focus()` quebraria num array.
const categoryInputEl = ref<HTMLInputElement | null>(null)
const setCategoryInputEl = (el: Element | null) => {
  categoryInputEl.value = el as HTMLInputElement | null
}
const savingCategory = ref(false)
const categoryError = ref('')

const startEditingCategory = async (tx: TransactionRow) => {
  editingCategoryId.value = tx.id
  editingCategoryValue.value = tx.category
  categoryError.value = ''
  await nextTick()
  categoryInputEl.value?.focus()
  categoryInputEl.value?.select()
}

const cancelEditingCategory = () => {
  editingCategoryId.value = null
  categoryError.value = ''
}

const saveCategory = async (tx: TransactionRow) => {
  const value = editingCategoryValue.value.trim()
  if (!value) {
    categoryError.value = 'Informe uma categoria.'
    return
  }
  savingCategory.value = true
  categoryError.value = ''
  try {
    const updated = await patch<TransactionRow>(`/transactions/${tx.id}/category/`, { category: value })
    if (updated) {
      tx.category = updated.category
      tx.category_is_manual = updated.category_is_manual
    }
    editingCategoryId.value = null
    await Promise.all([refreshCategories(), refreshStats()])
  } catch (e: unknown) {
    categoryError.value = extractApiError(e, 'Erro ao salvar a categoria.')
  } finally {
    savingCategory.value = false
  }
}

// Apaga a escolha manual e volta para a categoria automática (regras + Pluggy).
const resetCategory = async (tx: TransactionRow) => {
  savingCategory.value = true
  categoryError.value = ''
  try {
    const updated = await del<TransactionRow>(`/transactions/${tx.id}/category/`)
    if (updated) {
      tx.category = updated.category
      tx.category_is_manual = updated.category_is_manual
    }
    await Promise.all([refreshCategories(), refreshStats()])
  } catch (e: unknown) {
    categoryError.value = extractApiError(e, 'Erro ao restaurar a categoria automática.')
  } finally {
    savingCategory.value = false
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

const inputClass
  = 'w-full rounded-lg border border-sepia-300 bg-white px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500'
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
        <div ref="columnsMenuRef" class="relative">
          <button
            type="button"
            class="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-sepia-300 bg-white px-3 py-1.5 text-xs font-medium text-sepia-700 hover:bg-sepia-50"
            @click="columnsMenuOpen = !columnsMenuOpen"
          >
            <Icon icon="mdi:view-column-outline" class="h-4 w-4" />
            Colunas
          </button>
          <div
            v-if="columnsMenuOpen"
            class="absolute right-0 z-10 mt-2 w-48 rounded-lg border border-sepia-200 bg-white p-2 shadow-md"
          >
            <label
              v-for="column in TABLE_COLUMNS" :key="column.key"
              class="flex items-center gap-2 rounded px-2 py-1.5 text-sm text-sepia-700 hover:bg-sepia-50"
            >
              <input
                type="checkbox"
                :checked="isColumnVisible(column.key)"
                class="rounded border-sepia-300 text-sepia-900 focus:ring-sepia-500"
                @change="toggleColumn(column.key)"
              >
              {{ column.label }}
            </label>
          </div>
        </div>
        <button
          type="button"
          :disabled="exporting || !count"
          class="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-lg bg-sepia-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-sepia-950 disabled:opacity-40"
          @click="exportCsv"
        >
          <Icon icon="mdi:download-outline" class="h-4 w-4" />
          {{ exporting ? 'Exportando...' : 'Exportar CSV' }}
        </button>
      </div>
    </div>

    <p v-if="exportError" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ exportError }}
    </p>

    <!-- Filtros -->
    <div class="rounded-lg border border-sepia-200 bg-white p-4 shadow-sm">
      <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div class="lg:col-span-2">
          <label class="mb-1 block text-xs font-medium text-sepia-700">Buscar na descrição</label>
          <div class="relative">
            <Icon icon="mdi:magnify" class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-sepia-400" />
            <input v-model="filters.search" type="search" placeholder="Ex: uber, mercado, salário" :class="[inputClass, 'pl-9']">
          </div>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Categoria</label>
          <select v-model="filters.category" :class="inputClass">
            <option value="">Todas</option>
            <option v-for="category in categories" :key="category" :value="category">{{ category }}</option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Tipo</label>
          <select v-model="filters.type" :class="inputClass">
            <option value="">Todos</option>
            <option value="credit">Receita</option>
            <option value="debit">Despesa</option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Período</label>
          <select v-model="periodPreset" :class="inputClass">
            <option v-for="preset in PERIOD_PRESETS" :key="preset.key" :value="preset.key">{{ preset.label }}</option>
            <option value="custom" disabled>Personalizado</option>
          </select>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">De</label>
          <input v-model="filters.start_date" type="date" :class="inputClass">
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Até</label>
          <input v-model="filters.end_date" type="date" :class="inputClass">
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Valor mínimo</label>
          <input v-model="filters.min_amount" type="number" step="0.01" min="0" placeholder="0,00" :class="inputClass">
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-sepia-700">Valor máximo</label>
          <input v-model="filters.max_amount" type="number" step="0.01" min="0" placeholder="Sem limite" :class="inputClass">
        </div>
      </div>

      <div class="mt-3 flex justify-end">
        <button
          type="button"
          :disabled="!hasActiveFilter"
          class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg bg-sepia-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-sepia-950 disabled:opacity-40"
          @click="clearFilters"
        >
          <Icon icon="mdi:filter-remove-outline" class="h-4 w-4" />
          Limpar filtros
        </button>
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
      <table class="w-full text-sm">
        <thead class="border-b border-sepia-200 bg-sepia-50">
          <tr>
            <th v-if="isColumnVisible('date')" class="px-4 py-3 text-left font-medium text-sepia-600">Data</th>
            <th v-if="isColumnVisible('description')" class="px-4 py-3 text-left font-medium text-sepia-600">Descrição</th>
            <th v-if="isColumnVisible('account')" class="px-4 py-3 text-left font-medium text-sepia-600">Conta</th>
            <th v-if="isColumnVisible('institution')" class="px-4 py-3 text-left font-medium text-sepia-600">Banco</th>
            <th v-if="isColumnVisible('category')" class="px-4 py-3 text-left font-medium text-sepia-600">Categoria</th>
            <th v-if="isColumnVisible('type')" class="px-4 py-3 text-left font-medium text-sepia-600">Tipo</th>
            <th v-if="isColumnVisible('amount')" class="px-4 py-3 text-right font-medium text-sepia-600">Valor</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="tx in transactions" :key="tx.id"
            :class="['border-b border-sepia-100 last:border-0', (isFutureTx(tx.booked_at) || tx.is_internal_transfer) ? 'opacity-60' : '']"
          >
            <td v-if="isColumnVisible('date')" class="whitespace-nowrap px-4 py-3 text-sepia-500">
              {{ formatIsoDateOnly(tx.booked_at) }}
              <span v-if="isFutureTx(tx.booked_at)" class="ml-1.5 inline-block whitespace-nowrap rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                Previsto
              </span>
            </td>
            <td v-if="isColumnVisible('description')" class="px-4 py-3 font-medium text-sepia-900">{{ tx.description }}</td>
            <td v-if="isColumnVisible('account')" class="px-4 py-3 text-sepia-600">{{ tx.account_name || '—' }}</td>
            <td v-if="isColumnVisible('institution')" class="px-4 py-3 text-sepia-600">{{ tx.institution_name || '—' }}</td>
            <td v-if="isColumnVisible('category')" class="px-4 py-3">
              <div v-if="editingCategoryId === tx.id" class="flex flex-col gap-1">
                <div class="flex items-center gap-1">
                  <input
                    :ref="setCategoryInputEl"
                    v-model="editingCategoryValue"
                    type="text"
                    list="category-suggestions"
                    :disabled="savingCategory"
                    class="w-32 rounded border border-sepia-300 bg-white px-1.5 py-0.5 text-xs focus:border-sepia-500 focus:outline-none"
                    @keydown.enter="saveCategory(tx)"
                    @keydown.escape="cancelEditingCategory"
                  >
                  <button
                    type="button"
                    :disabled="savingCategory"
                    class="shrink-0 text-azul-600 hover:text-azul-700 disabled:opacity-40"
                    title="Salvar"
                    @click="saveCategory(tx)"
                  >
                    <Icon icon="mdi:check" class="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    :disabled="savingCategory"
                    class="shrink-0 text-sepia-400 hover:text-sepia-600 disabled:opacity-40"
                    title="Cancelar"
                    @click="cancelEditingCategory"
                  >
                    <Icon icon="mdi:close" class="h-4 w-4" />
                  </button>
                </div>
                <p v-if="categoryError" class="text-[10px] leading-tight text-vermelho-600">{{ categoryError }}</p>
              </div>
              <div v-else class="group flex items-center gap-1">
                <button
                  type="button"
                  class="inline-flex items-center gap-1 whitespace-nowrap rounded bg-sepia-100 px-2 py-0.5 text-xs text-sepia-600 hover:bg-sepia-200"
                  title="Clique para editar a categoria"
                  @click="startEditingCategory(tx)"
                >
                  {{ tx.category || 'Sem categoria' }}
                  <Icon v-if="tx.category_is_manual" icon="mdi:pencil" class="h-3 w-3 text-sepia-400" />
                </button>
                <button
                  v-if="tx.category_is_manual"
                  type="button"
                  class="shrink-0 text-sepia-300 opacity-0 hover:text-sepia-500 group-hover:opacity-100"
                  title="Restaurar categoria automática"
                  @click="resetCategory(tx)"
                >
                  <Icon icon="mdi:restore" class="h-3.5 w-3.5" />
                </button>
              </div>
            </td>
            <td v-if="isColumnVisible('type')" class="px-4 py-3">
              <span :class="['inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', typeBadge(tx)]">
                {{ typeLabel(tx) }}
              </span>
            </td>
            <td v-if="isColumnVisible('amount')" :class="['whitespace-nowrap px-4 py-3 text-right font-mono font-medium', tx.is_internal_transfer ? 'text-sepia-500' : (tx.type === 'credit' ? 'text-azul-600' : 'text-vermelho-600'), blur]">
              {{ tx.is_internal_transfer ? '' : (tx.type === 'credit' ? '+' : '-') }}{{ formatBRL(Math.abs(Number(tx.amount))) }}
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="totalPages > 1" class="flex items-center justify-between border-t border-sepia-200 px-4 py-3">
        <button
          type="button"
          :disabled="!hasPrevious || loading"
          class="whitespace-nowrap rounded-lg bg-sepia-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-sepia-950 disabled:opacity-40"
          @click="previous"
        >
          Anterior
        </button>
        <span class="text-xs text-sepia-500">Página {{ page }} de {{ totalPages }}</span>
        <button
          type="button"
          :disabled="!hasNext || loading"
          class="whitespace-nowrap rounded-lg bg-sepia-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-sepia-950 disabled:opacity-40"
          @click="next"
        >
          Próxima
        </button>
      </div>
    </div>

    <datalist id="category-suggestions">
      <option v-for="category in categories" :key="category" :value="category" />
    </datalist>
  </section>
</template>
