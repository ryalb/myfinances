export type FinancialFreedomProjection = {
  currentNetWorth: number
  monthlySavings: number
  averageMonthlyExpenses: number
  targetNetWorth: number
  estimatedPassiveIncome: number
  financialRunwayMonths: number
  estimatedRetireDate: string | null
  monthsToFreedom: number
  targetReached: boolean
  conservativeMonths: number
  baseMonths: number
  aggressiveMonths: number
}

const PROJECTION_QUERY = `{
  financialFreedomProjection {
    currentNetWorth
    monthlySavings
    averageMonthlyExpenses
    targetNetWorth
    estimatedPassiveIncome
    financialRunwayMonths
    estimatedRetireDate
    monthsToFreedom
    targetReached
    conservativeMonths
    baseMonths
    aggressiveMonths
  }
}`

export function useFinancialFreedom() {
  const { graphql } = useApi()

  const { data: projection, refresh } = useAsyncData<FinancialFreedomProjection | null>(
    'financial-freedom-projection',
    async () => {
      const res = await graphql<{ data?: { financialFreedomProjection?: FinancialFreedomProjection | null } }>(PROJECTION_QUERY)
      return res?.data?.financialFreedomProjection ?? null
    },
    { default: () => null },
  )

  return { projection, refresh }
}
