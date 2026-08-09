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
  const config = useRuntimeConfig()
  const router = useRouter()
  const { logout } = useAuth()

  const { data: projection, refresh } = useAsyncData<FinancialFreedomProjection | null>(
    'financial-freedom-projection',
    async () => {
      try {
        const res = await $fetch<{ data?: { financialFreedomProjection?: FinancialFreedomProjection | null } }>(
          `${config.public.graphqlEndpoint}`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${useCookie<string | null>('access_token').value}`,
              'Content-Type': 'application/json',
            },
            body: { query: PROJECTION_QUERY },
          }
        )
        return res?.data?.financialFreedomProjection ?? null
      } catch (error) {
        if ((error as { status?: number }).status === 401) {
          const path = router.currentRoute.value.path
          const isAuthPage = path === '/login' || path === '/register'
          if (!isAuthPage) {
            logout()
            await router.push('/login')
          }
        }
        return null
      }
    },
    { default: () => null },
  )

  return { projection, refresh }
}
