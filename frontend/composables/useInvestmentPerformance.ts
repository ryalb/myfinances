import { useInvestments, type InvestmentGroup, type InvestmentRow } from '@/composables/useInvestments'
import { useMarketBenchmarks, type BenchmarkWindow } from '@/composables/useMarketBenchmarks'

// "Ainda vale a pena?" respondido contra o CDI: e o custo de oportunidade de
// qualquer aplicacao (Tesouro Selic / CDB 100% CDI rendem isso com risco quase
// zero e liquidez diaria). Um ativo que rende menos que o CDI no mesmo periodo
// esta, na pratica, pagando para o investidor correr mais risco.
export type VerdictStatus = 'keep' | 'watch' | 'review' | 'unknown'

export type Verdict = {
  status: VerdictStatus
  label: string
  // Janela usada na comparacao -- o veredito sempre diz em que se baseou.
  basis: string | null
  investmentReturn: number | null
  cdiReturn: number | null
  // Rendimento como % do CDI (100 = empatou com o CDI).
  pctOfCdi: number | null
  reason: string
}

export type PerformanceRow = InvestmentRow & { verdict: Verdict }

export type WindowSummary = {
  // Media ponderada pelo valor de mercado, so dos ativos com dado na janela.
  rate: number | null
  // Fatia (0-100) do valor da categoria que tem dado nessa janela -- uma media
  // calculada com 10% da carteira nao representa a categoria.
  coverage: number
}

export type CategorySummary = InvestmentGroup & {
  share: number
  rows: PerformanceRow[]
  windows: Record<BenchmarkWindow, WindowSummary>
  verdictCounts: Record<VerdictStatus, number>
}

export const VERDICT_LABELS: Record<VerdictStatus, string> = {
  keep: 'Vale manter',
  watch: 'Atenção',
  review: 'Reavaliar',
  unknown: 'Sem dados',
}

// Faixa intermediaria em vez de corte seco em 100%: renda fixa isenta de IR
// (LCI/LCA, CRA, debenture incentivada) a 85-90% do CDI empata com um CDB
// tributado a 100%, entao abaixo do CDI nao e automaticamente ruim.
const KEEP_MIN_PCT_OF_CDI = 100
const WATCH_MIN_PCT_OF_CDI = 80

// Abaixo disso o "desde a compra" e curto demais para julgar (mesmo motivo de
// nao dar veredito com so 1 mes de historico).
const MIN_HELD_DAYS_FOR_VERDICT = 90

// Acoes e FIIs: o valor de mercado nao inclui dividendos/rendimentos ja pagos,
// entao o rendimento aqui subestima o retorno total.
export const PRICE_ONLY_CATEGORIES = new Set(['equity_br', 'equity_intl', 'fii', 'etf'])

const pct = (v: number) =>
  `${v > 0 ? '+' : ''}${v.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`

const statusFor = (investmentReturn: number, pctOfCdi: number): VerdictStatus => {
  if (investmentReturn < 0) return 'review'
  if (pctOfCdi >= KEEP_MIN_PCT_OF_CDI) return 'keep'
  if (pctOfCdi >= WATCH_MIN_PCT_OF_CDI) return 'watch'
  return 'review'
}

export function useInvestmentPerformance() {
  const investments = useInvestments()
  const { rows, groups, totalValue } = investments

  const sinceDates = computed(() =>
    Array.from(new Set(rows.value.map((row) => row.purchaseDate).filter((d): d is string => !!d))).sort(),
  )
  const market = useMarketBenchmarks(sinceDates)
  const { cdi, cdiSince } = market

  const verdictFor = (row: InvestmentRow): Verdict => {
    // Janela mais longa disponivel primeiro: 12 meses, desde a compra, 3 meses.
    const candidates: { basis: string; investmentReturn: number | null; cdiReturn: number | null }[] = [
      { basis: '12 meses', investmentReturn: row.lastTwelveMonthsRate, cdiReturn: cdi('m12') },
      {
        basis: row.heldDays ? `desde a compra (${Math.round(row.heldDays / 30)} meses)` : 'desde a compra',
        investmentReturn: row.heldDays !== null && row.heldDays >= MIN_HELD_DAYS_FOR_VERDICT ? row.sincePurchaseRate : null,
        cdiReturn: cdiSince(row.purchaseDate),
      },
      { basis: '3 meses', investmentReturn: row.threeMonthRate, cdiReturn: cdi('m3') },
    ]
    const chosen = candidates.find((c) => c.investmentReturn !== null && c.cdiReturn !== null && c.cdiReturn > 0)

    if (!chosen) {
      const hasAnyReturn = row.lastMonthRate !== null || row.sincePurchaseRate !== null
      return {
        status: 'unknown',
        label: VERDICT_LABELS.unknown,
        basis: null,
        investmentReturn: null,
        cdiReturn: null,
        pctOfCdi: null,
        reason: hasAnyReturn
          ? 'Histórico ainda curto (menos de 3 meses) para comparar com o CDI com segurança.'
          : 'Sem rendimento informado pela instituição nem histórico suficiente para estimar.',
      }
    }

    const investmentReturn = chosen.investmentReturn as number
    const cdiReturn = chosen.cdiReturn as number
    const pctOfCdi = (investmentReturn / cdiReturn) * 100
    const status = statusFor(investmentReturn, pctOfCdi)

    let reason = `${pct(investmentReturn)} em ${chosen.basis} contra ${pct(cdiReturn)} do CDI`
    reason += investmentReturn > 0 ? ` (${Math.round(pctOfCdi)}% do CDI).` : '.'
    if (status === 'watch') reason += ' Abaixo do CDI — só compensa se for isento de IR ou tiver outro objetivo.'
    if (status === 'review') {
      reason += investmentReturn < 0
        ? ' Está perdendo dinheiro no período.'
        : ' Rende bem menos que uma aplicação pós-fixada simples.'
    }
    if (PRICE_ONLY_CATEGORIES.has(row.investment.display_category)) {
      reason += ' Considera só a variação de preço, sem dividendos/rendimentos pagos.'
    }

    return { status, label: VERDICT_LABELS[status], basis: chosen.basis, investmentReturn, cdiReturn, pctOfCdi, reason }
  }

  const performanceRows = computed<PerformanceRow[]>(() =>
    rows.value.map((row) => ({ ...row, verdict: verdictFor(row) })),
  )

  const verdictById = computed(() => {
    const byId = new Map<number, Verdict>()
    for (const row of performanceRows.value) byId.set(row.investment.id, row.verdict)
    return byId
  })

  const RATE_FIELD: Record<BenchmarkWindow, 'lastMonthRate' | 'threeMonthRate' | 'lastTwelveMonthsRate'> = {
    m1: 'lastMonthRate',
    m3: 'threeMonthRate',
    m12: 'lastTwelveMonthsRate',
  }

  const summarizeWindow = (rowsInScope: InvestmentRow[], window: BenchmarkWindow): WindowSummary => {
    const total = rowsInScope.reduce((sum, row) => sum + row.marketValue, 0)
    let weighted = 0
    let covered = 0
    for (const row of rowsInScope) {
      const rate = row[RATE_FIELD[window]]
      if (rate === null || row.marketValue <= 0) continue
      weighted += rate * row.marketValue
      covered += row.marketValue
    }
    return {
      rate: covered > 0 ? weighted / covered : null,
      coverage: total > 0 ? (covered / total) * 100 : 0,
    }
  }

  const summarizeWindows = (rowsInScope: InvestmentRow[]) => ({
    m1: summarizeWindow(rowsInScope, 'm1'),
    m3: summarizeWindow(rowsInScope, 'm3'),
    m12: summarizeWindow(rowsInScope, 'm12'),
  })

  const countVerdicts = (rowsInScope: PerformanceRow[]) => {
    const counts: Record<VerdictStatus, number> = { keep: 0, watch: 0, review: 0, unknown: 0 }
    for (const row of rowsInScope) counts[row.verdict.status] += 1
    return counts
  }

  const categories = computed<CategorySummary[]>(() =>
    groups.value.map((group) => {
      const groupRows = group.rows
        .map((row) => ({ ...row, verdict: verdictById.value.get(row.investment.id) as Verdict }))
        .sort((a, b) => b.marketValue - a.marketValue)
      return {
        ...group,
        rows: groupRows,
        share: totalValue.value > 0 ? (group.totalValue / totalValue.value) * 100 : 0,
        windows: summarizeWindows(groupRows),
        verdictCounts: countVerdicts(groupRows),
      }
    }),
  )

  const portfolioWindows = computed(() => summarizeWindows(rows.value))
  const portfolioVerdictCounts = computed(() => countVerdicts(performanceRows.value))

  // Piores primeiro: "reavaliar" antes de "atencao", e dentro de cada um o
  // maior valor primeiro (onde a decisao pesa mais na carteira).
  const needsAttention = computed(() => {
    const order: Record<VerdictStatus, number> = { review: 0, watch: 1, keep: 2, unknown: 3 }
    return performanceRows.value
      .filter((row) => row.verdict.status === 'review' || row.verdict.status === 'watch')
      .sort((a, b) => order[a.verdict.status] - order[b.verdict.status] || b.marketValue - a.marketValue)
  })

  return {
    ...investments,
    market,
    performanceRows,
    categories,
    portfolioWindows,
    portfolioVerdictCounts,
    needsAttention,
  }
}
