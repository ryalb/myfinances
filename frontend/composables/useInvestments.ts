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
  estimated_amount_original: string | null
  status: string
  purchase_date: string | null
  grace_period_date: string | null
}

export type InvestmentRow = {
  investment: Investment
  position: InvestmentPosition | null
  marketValue: number
  lastMonthRate: number | null
  threeMonthRate: number | null
  lastTwelveMonthsRate: number | null
  annualRate: number | null
  amountProfit: number | null
  amountOriginal: number | null
  purchaseDate: string | null
  heldDays: number | null
  sincePurchaseRate: number | null
  sincePurchaseAnnualRate: number | null
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

export const compareCategoryKeys = (a: string, b: string): number => {
  const orderA = CATEGORY_ORDER.indexOf(a)
  const orderB = CATEGORY_ORDER.indexOf(b)
  return (orderA === -1 ? CATEGORY_ORDER.length : orderA) - (orderB === -1 ? CATEGORY_ORDER.length : orderB)
}

// So a lista de ativos, sem posicoes: o menu lateral usa para montar o
// submenu de categorias. Mesma chave de cache que `useInvestments`, entao as
// duas telas compartilham a mesma requisicao.
export function useInvestmentList() {
  const { get } = useApi()
  return useAsyncData<Investment[]>(
    'investments',
    async () => (await get<Investment[]>('/investments/')) || [],
    { default: () => [] },
  )
}

export function useInvestments() {
  const { get } = useApi()

  const { data: investments, refresh: refreshInvestments } = useInvestmentList()

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

  const positionsByInvestment = computed(() => {
    const byInvestment = new Map<number, InvestmentPosition[]>()
    for (const position of positions.value || []) {
      const list = byInvestment.get(position.investment)
      if (list) list.push(position)
      else byInvestment.set(position.investment, [position])
    }
    for (const list of byInvestment.values()) {
      list.sort((a, b) => new Date(a.as_of_date).getTime() - new Date(b.as_of_date).getTime())
    }
    return byInvestment
  })

  const MS_PER_DAY = 24 * 60 * 60 * 1000

  // A Pluggy nem sempre manda `lastMonthRate`/`lastTwelveMonthsRate` (visto em
  // Renda Fixa e Acoes/FIIs igualmente) -- quando falta, estima a partir do
  // historico local de posicoes (`InvestmentPosition` guarda uma linha por dia
  // sincronizado). So estima se achar uma posicao proxima o bastante da data alvo
  // e com a mesma quantidade: se a quantidade mudou no meio (aporte/resgate), a
  // variacao de `market_value` mistura rendimento com movimentacao de caixa e o
  // numero sai errado, entao prefere '-' a um numero enganoso.
  const estimateRate = (
    investmentId: number,
    referenceDate: string,
    currentQuantity: number,
    currentValue: number,
    targetDaysAgo: number,
    toleranceDays: number,
  ): number | null => {
    const list = positionsByInvestment.value.get(investmentId)
    if (!list || list.length < 2) return null

    const targetTime = new Date(referenceDate).getTime() - targetDaysAgo * MS_PER_DAY

    let closest: InvestmentPosition | null = null
    let closestDiff = Infinity
    for (const position of list) {
      const diff = Math.abs(new Date(position.as_of_date).getTime() - targetTime)
      if (diff < closestDiff) {
        closest = position
        closestDiff = diff
      }
    }
    if (!closest || closestDiff > toleranceDays * MS_PER_DAY) return null
    if (toNumber(closest.quantity) !== currentQuantity) return null

    const oldValue = toNumber(closest.market_value)
    if (oldValue === null || oldValue <= 0) return null
    return (currentValue / oldValue - 1) * 100
  }

  const rows = computed<InvestmentRow[]>(() => {
    return (investments.value || []).map((investment) => {
      const position = latestPositionByInvestment.value.get(investment.id) || null
      const marketValue = toNumber(position?.market_value) || 0
      // `amount_original` bruto da Pluggy, com fallback pro custo medio estimado
      // via `InvestmentTransaction` (backend so preenche esse quando falta o
      // bruto -- ver `investment_cost_basis.py`).
      const amountOriginal =
        toNumber(position?.amount_original ?? null) ??
        toNumber(position?.estimated_amount_original ?? null)
      const quantity = toNumber(position?.quantity ?? null)

      // Fallback de lucro: mesma formula recomendada pela propria Pluggy quando
      // `amountProfit` vem nulo (valor atual - valor originalmente investido).
      let amountProfit = toNumber(position?.amount_profit ?? null)
      if (amountProfit === null && amountOriginal !== null) {
        amountProfit = marketValue - amountOriginal
      }

      let lastMonthRate = toNumber(position?.last_month_rate ?? null)
      let lastTwelveMonthsRate = toNumber(position?.last_twelve_months_rate ?? null)
      // A Pluggy nao tem campo de 3 meses: sempre estimado pelo historico local.
      let threeMonthRate: number | null = null
      if (position && quantity !== null) {
        if (lastMonthRate === null) {
          lastMonthRate = estimateRate(investment.id, position.as_of_date, quantity, marketValue, 30, 7)
        }
        threeMonthRate = estimateRate(investment.id, position.as_of_date, quantity, marketValue, 91, 10)
        if (lastTwelveMonthsRate === null) {
          lastTwelveMonthsRate = estimateRate(investment.id, position.as_of_date, quantity, marketValue, 365, 20)
        }
      }

      // Rendimento desde a compra: unica janela disponivel para quem ainda nao
      // tem historico local longo (renda fixa costuma trazer `purchase_date` e
      // valor aplicado). Anualizado so a partir de 30 dias -- abaixo disso a
      // extrapolacao para 1 ano amplifica ruido de marcacao a mercado.
      const purchaseDate = position?.purchase_date || null
      let heldDays: number | null = null
      let sincePurchaseRate: number | null = null
      let sincePurchaseAnnualRate: number | null = null
      if (purchaseDate && position) {
        heldDays = Math.round(
          (new Date(position.as_of_date).getTime() - new Date(purchaseDate).getTime()) / MS_PER_DAY,
        )
      }
      if (amountOriginal !== null && amountOriginal > 0 && marketValue > 0) {
        sincePurchaseRate = (marketValue / amountOriginal - 1) * 100
        if (heldDays !== null && heldDays >= 30) {
          sincePurchaseAnnualRate = (Math.pow(marketValue / amountOriginal, 365 / heldDays) - 1) * 100
        }
      }

      return {
        investment,
        position,
        marketValue,
        lastMonthRate,
        threeMonthRate,
        lastTwelveMonthsRate,
        annualRate: toNumber(position?.annual_rate ?? null),
        amountProfit,
        amountOriginal,
        purchaseDate,
        heldDays,
        sincePurchaseRate,
        sincePurchaseAnnualRate,
      }
    })
  })

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
    return Array.from(byCategory.values()).sort((a, b) => compareCategoryKeys(a.key, b.key))
  })

  const totalValue = computed(() => rows.value.reduce((sum, row) => sum + row.marketValue, 0))
  const totalProfit = computed(() => rows.value.reduce((sum, row) => sum + (row.amountProfit || 0), 0))

  return {
    investments,
    positions,
    rows,
    groups,
    totalValue,
    totalProfit,
    refresh,
  }
}
