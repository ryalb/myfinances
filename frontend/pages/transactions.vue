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

const { get, download } = useApi()

// Categorias vêm dos dados, não de um enum: podem chegar da Pluggy, de uma regra do
// usuário ou das palavras-chave.
const { data: categories } = await useAsyncData(
  'transaction-categories',
  async () => (await get<string[]>('/transactions/categories/')) || [],
  { default: () => [] },
)

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
  return tx.type === 'credit' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
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
        <button
          type="button"
          :disabled="exporting || !count"
          class="inline-flex items-center gap-2 rounded-lg border border-sepia-200 bg-white px-3 py-1.5 text-xs font-medium text-sepia-600 hover:bg-sepia-50 disabled:opacity-40"
          @click="exportCsv"
        >
          <Icon icon="mdi:download-outline" class="h-4 w-4" />
          {{ exporting ? 'Exportando...' : 'Exportar CSV' }}
        </button>
      </div>
    </div>

    <p v-if="exportError" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ exportError }}
    </p>

    <!-- Filtros -->
    <div class="rounded-xl border border-sepia-200 bg-white p-4 shadow-sm">
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

      <div v-if="hasActiveFilter" class="mt-3 flex justify-end">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-sepia-600 hover:bg-sepia-50"
          @click="clearFilters"
        >
          <Icon icon="mdi:filter-remove-outline" class="h-4 w-4" />
          Limpar filtros
        </button>
      </div>
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

    <div v-else class="overflow-hidden rounded-xl border border-sepia-200 bg-white shadow-sm">
      <table class="w-full text-sm">
        <thead class="border-b border-sepia-200 bg-sepia-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Data</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Descrição</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Conta</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Banco</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Categoria</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Tipo</th>
            <th class="px-4 py-3 text-right font-medium text-sepia-600">Valor</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="tx in transactions" :key="tx.id"
            :class="['border-b border-sepia-100 last:border-0', (isFutureTx(tx.booked_at) || tx.is_internal_transfer) ? 'opacity-60' : '']"
          >
            <td class="whitespace-nowrap px-4 py-3 text-sepia-500">
              {{ formatIsoDateOnly(tx.booked_at) }}
              <span v-if="isFutureTx(tx.booked_at)" class="ml-1.5 inline-block whitespace-nowrap rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                Previsto
              </span>
            </td>
            <td class="px-4 py-3 font-medium text-sepia-900">{{ tx.description }}</td>
            <td class="px-4 py-3 text-sepia-600">{{ tx.account_name || '—' }}</td>
            <td class="px-4 py-3 text-sepia-600">{{ tx.institution_name || '—' }}</td>
            <td class="px-4 py-3">
              <span v-if="tx.category" class="inline-block whitespace-nowrap rounded bg-sepia-100 px-2 py-0.5 text-xs text-sepia-600">
                {{ tx.category }}
              </span>
              <span v-else class="text-sepia-400">—</span>
            </td>
            <td class="px-4 py-3">
              <span :class="['inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', typeBadge(tx)]">
                {{ typeLabel(tx) }}
              </span>
            </td>
            <td :class="['whitespace-nowrap px-4 py-3 text-right font-medium', tx.is_internal_transfer ? 'text-sepia-500' : (tx.type === 'credit' ? 'text-emerald-600' : 'text-rose-600'), blur]">
              {{ tx.is_internal_transfer ? '' : (tx.type === 'credit' ? '+' : '-') }}{{ formatBRL(Math.abs(Number(tx.amount))) }}
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="totalPages > 1" class="flex items-center justify-between border-t border-sepia-200 px-4 py-3">
        <button
          type="button"
          :disabled="!hasPrevious || loading"
          class="rounded-lg border border-sepia-200 bg-white px-3 py-1.5 text-xs font-medium text-sepia-600 hover:bg-sepia-50 disabled:opacity-40"
          @click="previous"
        >
          Anterior
        </button>
        <span class="text-xs text-sepia-500">Página {{ page }} de {{ totalPages }}</span>
        <button
          type="button"
          :disabled="!hasNext || loading"
          class="rounded-lg border border-sepia-200 bg-white px-3 py-1.5 text-xs font-medium text-sepia-600 hover:bg-sepia-50 disabled:opacity-40"
          @click="next"
        >
          Próxima
        </button>
      </div>
    </div>
  </section>
</template>
