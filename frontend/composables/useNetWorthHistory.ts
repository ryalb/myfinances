export function useNetWorthHistory() {
  const { get } = useApi()

  const { data: history, refresh } = useAsyncData(
    'net-worth-history',
    async () => {
      return await get<{ date: string; net_worth: number; assets: number; liabilities: number }[]>(`/net-worth/snapshot/`) || []
    },
    { default: () => [] },
  )

  return { history, refresh }
}
