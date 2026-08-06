export function useCashFlowHistory() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

  const { data: history, refresh } = useState<{
    year: number
    month: number
    income: number
    expenses: number
    savings: number
    savings_rate: number
  }[]>('cash-flow-history', async () => {
    try {
      return await $fetch(`${config.public.apiBaseUrl}/cash-flow/`, { headers })
    } catch {
      return []
    }
  })

  return { history, refresh }
}
