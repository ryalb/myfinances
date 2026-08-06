export function useNetWorthHistory() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

  const { data: history, refresh } = useState<{
    id: number
    date: string
    assets: number
    liabilities: number
    net_worth: number
  }[]>('net-worth-history', async () => {
    try {
      return await $fetch(`${config.public.apiBaseUrl}/net-worth/snapshot/`, { headers })
    } catch {
      return []
    }
  })

  return { history, refresh }
}
