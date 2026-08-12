export type MonthlyCashFlowPoint = {
  year: number
  month: number
  income: number
  expenses: number
  savings: number
  savings_rate: number
}

export type CategoryDelta = {
  category: string
  current_amount: number
  previous_amount: number
  delta: number
}

export type MonthlyReviewRecord = {
  id: number
  year: number
  month: number
  adjustments: string[]
  completed_at: string | null
  created_at: string
  updated_at: string
}

export type MonthlyReviewSummary = {
  review: MonthlyReviewRecord
  net_worth_delta: number | null
  current_net_worth: number | null
  savings_rate_trend: MonthlyCashFlowPoint[]
  category_deltas: CategoryDelta[]
  achievements: string[]
}

/**
 * Ritual mensal de revisão financeira.
 *
 * `year`/`month` são estado do próprio composable (não da página): a navegação
 * entre meses e o refetch andam juntos, e cada tela que precisasse disso teria
 * que replicar a lógica de "virar o mês" na mão.
 */
export function useMonthlyReview() {
  const { get, patch } = useApi()

  const today = new Date()
  const year = ref(today.getFullYear())
  const month = ref(today.getMonth() + 1)

  const isCurrentMonth = computed(
    () => year.value === today.getFullYear() && month.value === today.getMonth() + 1,
  )

  const queryString = computed(() => `year=${year.value}&month=${month.value}`)

  const { data: summary, refresh, status } = useAsyncData<MonthlyReviewSummary | null>(
    'monthly-review',
    () => get<MonthlyReviewSummary>(`/monthly-review/?${queryString.value}`),
    { default: () => null, watch: [queryString] },
  )

  const loading = computed(() => status.value === 'pending')

  const previousMonth = () => {
    if (month.value === 1) {
      month.value = 12
      year.value -= 1
    } else {
      month.value -= 1
    }
  }

  const nextMonth = () => {
    if (isCurrentMonth.value) return
    if (month.value === 12) {
      month.value = 1
      year.value += 1
    } else {
      month.value += 1
    }
  }

  const saveAdjustments = async (adjustments: string[]) => {
    await patch(`/monthly-review/?${queryString.value}`, { adjustments })
    await refresh()
  }

  const markCompleted = async (completed: boolean) => {
    await patch(`/monthly-review/?${queryString.value}`, { completed })
    await refresh()
  }

  return {
    summary,
    loading,
    year,
    month,
    isCurrentMonth,
    previousMonth,
    nextMonth,
    saveAdjustments,
    markCompleted,
    refresh,
  }
}
