export function useFinancialFreedom() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const headers = token.value ? { Authorization: `Bearer ${token.value}`, 'Content-Type': 'application/json' } : {}

  const { data: projection, refresh } = useState<{
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
  } | null>('financial-freedom-projection', async () => {
    try {
      const res = await $fetch(`${config.public.graphqlEndpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query: `{ financialFreedomProjection { currentNetWorth monthlySavings averageMonthlyExpenses targetNetWorth estimatedPassiveIncome financialRunwayMonths estimatedRetireDate monthsToFreedom targetReached conservativeMonths baseMonths aggressiveMonths } }`,
        }),
      })
      return res.data?.financialFreedomProjection || null
    } catch {
      return null
    }
  })

  return { projection, refresh }
}
