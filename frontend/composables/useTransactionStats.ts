export type CategoryTotal = {
  category: string
  total: number
  count: number
  percentage: number
}

export type TransactionStats = {
  total_income: number
  total_expenses: number
  balance: number
  transaction_count: number
  average_expense: number
  expense_categories: CategoryTotal[]
  income_categories: CategoryTotal[]
}

const EMPTY_STATS: TransactionStats = {
  total_income: 0,
  total_expenses: 0,
  balance: 0,
  transaction_count: 0,
  average_expense: 0,
  expense_categories: [],
  income_categories: [],
}

const toCategoryTotal = (row: { category: string, total: string, count: number, percentage: string }): CategoryTotal => ({
  category: row.category,
  total: Number(row.total),
  count: row.count,
  percentage: Number(row.percentage),
})

/**
 * Estatísticas e totais por categoria da tela de transações -- mesmos filtros
 * da listagem (`params`), para os cards e gráficos baterem com o que está na
 * tabela.
 */
export function useTransactionStats(params: () => Record<string, string>) {
  const { get } = useApi()

  const queryString = computed(() => {
    const query = new URLSearchParams()
    for (const [name, value] of Object.entries(params())) {
      if (value !== '' && value != null) query.set(name, value)
    }
    return query.toString()
  })

  const { data, status, refresh } = useAsyncData(
    'transaction-stats',
    async () => {
      // `DecimalField` do DRF serializa como string por padrão ("150.00"),
      // então os totais e percentuais chegam como texto -- convertidos aqui
      // para os componentes receberem números prontos para exibir.
      const raw = await get<{
        total_income: string
        total_expenses: string
        balance: string
        transaction_count: number
        average_expense: string
        expense_categories: { category: string, total: string, count: number, percentage: string }[]
        income_categories: { category: string, total: string, count: number, percentage: string }[]
      }>(`/transactions/stats/?${queryString.value}`)

      if (!raw) return EMPTY_STATS

      return {
        total_income: Number(raw.total_income),
        total_expenses: Number(raw.total_expenses),
        balance: Number(raw.balance),
        transaction_count: raw.transaction_count,
        average_expense: Number(raw.average_expense),
        expense_categories: raw.expense_categories.map(toCategoryTotal),
        income_categories: raw.income_categories.map(toCategoryTotal),
      }
    },
    { default: () => EMPTY_STATS, watch: [queryString] },
  )

  return {
    stats: data,
    loading: computed(() => status.value === 'pending'),
    refresh,
  }
}
