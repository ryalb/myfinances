export type PortfolioConcentrationRow = {
  key: string
  label: string
  amount: string
  percentage: string
}

export type PortfolioCurrencyExposure = {
  brl_amount: string
  brl_percentage: string
  foreign_amount: string
  foreign_percentage: string
  by_currency: PortfolioConcentrationRow[]
}

export type PortfolioRisk = {
  issuer_concentration: PortfolioConcentrationRow[]
  indexer_concentration: PortfolioConcentrationRow[]
  currency_exposure: PortfolioCurrencyExposure
}

const EMPTY: PortfolioRisk = {
  issuer_concentration: [],
  indexer_concentration: [],
  currency_exposure: {
    brl_amount: '0',
    brl_percentage: '0',
    foreign_amount: '0',
    foreign_percentage: '0',
    by_currency: [],
  },
}

// DRF serializa `DecimalField` como string -- mesma conversao de `useInvestments.ts`.
const toNumber = (v: string | null | undefined): number => {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

export function usePortfolioRisk() {
  const { get } = useApi()

  const { data: risk, refresh } = useAsyncData<PortfolioRisk>(
    'portfolio-risk',
    async () => (await get<PortfolioRisk>('/portfolio-risk/')) || EMPTY,
    { default: () => EMPTY },
  )

  // Mesmo formato `{key, label, value, percentage}` que `CompositionBar` ja usa
  // pela composicao por categoria (`useInvestments.compositionSegments`) --
  // reaproveita o componente em vez de duplicar a barra/legenda para cada risco.
  const toSegments = (rows: PortfolioConcentrationRow[]) =>
    rows.map((row) => ({
      key: row.key,
      label: row.label,
      value: toNumber(row.amount),
      percentage: toNumber(row.percentage),
    }))

  const issuerSegments = computed(() => toSegments(risk.value?.issuer_concentration || []))
  const indexerSegments = computed(() => toSegments(risk.value?.indexer_concentration || []))
  const currencySegments = computed(() => toSegments(risk.value?.currency_exposure.by_currency || []))

  return { risk, issuerSegments, indexerSegments, currencySegments, refresh }
}
