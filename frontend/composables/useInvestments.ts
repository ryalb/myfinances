export type Investment = {
  id: number
  name: string
  kind: string
  currency: string
  subtype: string
  code: string
  isin: string
  issuer: string
  issue_date: string | null
  due_date: string | null
  rate_type: string
  tax_exempt: boolean | null
  rate_periodicity: string
  indexer_additional_info: string
  display_category: string
  display_category_label: string
  display_category_estimated: boolean
}

export type InvestmentPosition = {
  id: number
  investment: number
  as_of_date: string
  quantity: string
  unit_price: string
  market_value: string
  last_month_rate: string | null
  last_twelve_months_rate: string | null
  annual_rate: string | null
  fixed_annual_rate: string | null
  rate: string | null
  amount_profit: string | null
  amount_original: string | null
  status: string
  purchase_date: string | null
  grace_period_date: string | null
}

export type InvestmentRow = {
  investment: Investment
  position: InvestmentPosition | null
  marketValue: number
  lastMonthRate: number | null
  lastTwelveMonthsRate: number | null
  annualRate: number | null
  amountProfit: number | null
  amountOriginal: number | null
}

export type InvestmentGroup = {
  key: string
  label: string
  estimated: boolean
  rows: InvestmentRow[]
  totalValue: number
  totalProfit: number
}

// DRF serializa `DecimalField` como string -- mesma conversao de
// `useDashboardMetrics.ts`. `null`/`''` (rate ainda nao sincronizado) fica null,
// nao 0: 0% de rendimento e um dado real, diferente de "sem dado".
const toNumber = (v: string | null | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export function useInvestments() {
  const { get } = useApi()

  const { data: investments, refresh: refreshInvestments } = useAsyncData<Investment[]>(
    'investments',
    async () => (await get<Investment[]>('/investments/')) || [],
    { default: () => [] },
  )

  const { data: positions, refresh: refreshPositions } = useAsyncData<InvestmentPosition[]>(
    'investment-positions',
    async () => (await get<InvestmentPosition[]>('/investment-positions/')) || [],
    { default: () => [] },
  )

  const refresh = async () => {
    await Promise.all([refreshInvestments(), refreshPositions()])
  }

  const latestPositionByInvestment = computed(() => {
    const byInvestment = new Map<number, InvestmentPosition>()
    for (const position of positions.value || []) {
      const current = byInvestment.get(position.investment)
      if (!current || new Date(position.as_of_date) > new Date(current.as_of_date)) {
        byInvestment.set(position.investment, position)
      }
    }
    return byInvestment
  })

  const rows = computed<InvestmentRow[]>(() => {
    return (investments.value || []).map((investment) => {
      const position = latestPositionByInvestment.value.get(investment.id) || null
      return {
        investment,
        position,
        marketValue: toNumber(position?.market_value) || 0,
        lastMonthRate: toNumber(position?.last_month_rate ?? null),
        lastTwelveMonthsRate: toNumber(position?.last_twelve_months_rate ?? null),
        annualRate: toNumber(position?.annual_rate ?? null),
        amountProfit: toNumber(position?.amount_profit ?? null),
        amountOriginal: toNumber(position?.amount_original ?? null),
      }
    })
  })

  // Ordem fixa em vez de alfabetica: renda fixa e acoes primeiro (o que a
  // maioria das carteiras concentra), especulativo/ambiguo por ultimo.
  const CATEGORY_ORDER = [
    'fixed_income',
    'equity_br',
    'fii',
    'equity_intl',
    'etf',
    'mutual_fund',
    'coe',
    'other',
  ]

  const groups = computed<InvestmentGroup[]>(() => {
    const byCategory = new Map<string, InvestmentGroup>()
    for (const row of rows.value) {
      const key = row.investment.display_category
      let group = byCategory.get(key)
      if (!group) {
        group = {
          key,
          label: row.investment.display_category_label,
          estimated: row.investment.display_category_estimated,
          rows: [],
          totalValue: 0,
          totalProfit: 0,
        }
        byCategory.set(key, group)
      }
      group.rows.push(row)
      group.totalValue += row.marketValue
      group.totalProfit += row.amountProfit || 0
    }
    return Array.from(byCategory.values()).sort((a, b) => {
      const orderA = CATEGORY_ORDER.indexOf(a.key)
      const orderB = CATEGORY_ORDER.indexOf(b.key)
      return (orderA === -1 ? CATEGORY_ORDER.length : orderA) - (orderB === -1 ? CATEGORY_ORDER.length : orderB)
    })
  })

  const totalValue = computed(() => rows.value.reduce((sum, row) => sum + row.marketValue, 0))
  const totalProfit = computed(() => rows.value.reduce((sum, row) => sum + (row.amountProfit || 0), 0))

  const compositionSegments = computed(() => {
    const total = totalValue.value
    if (total <= 0) return []
    return groups.value.map((group) => ({
      key: group.key,
      label: group.label,
      estimated: group.estimated,
      value: group.totalValue,
      percentage: (group.totalValue / total) * 100,
    }))
  })

  return {
    investments,
    positions,
    rows,
    groups,
    totalValue,
    totalProfit,
    compositionSegments,
    refresh,
  }
}
