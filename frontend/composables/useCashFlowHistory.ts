export function useCashFlowHistory() {
  const { get } = useApi()

  const { data: history, refresh } = useAsyncData(
    'cash-flow-history',
    async () => {
      return await get<{ year: number; month: number; income: number; expenses: number; savings: number; savings_rate: number }[]>(`/cash-flow/`) || []
    },
    { default: () => [] },
  )

  return { history, refresh }
}
