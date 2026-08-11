export type SubscriptionScheduleItem = {
  name: string
  category: string
  dueDate: string
  amount: number
  status: string
}

export type SubscriptionOverview = {
  monthlyRecurringTotal: number
  activeCount: number
  paidThisMonth: number
  pendingThisMonth: number
  overdueTotal: number
  overdue: SubscriptionScheduleItem[]
  upcoming: SubscriptionScheduleItem[]
}

const OVERVIEW_QUERY = `{
  subscriptionOverview {
    monthlyRecurringTotal
    activeCount
    paidThisMonth
    pendingThisMonth
    overdueTotal
    overdue { name category dueDate amount status }
    upcoming { name category dueDate amount status }
  }
}`

export function useSubscriptionOverview() {
  const { graphql } = useApi()

  const { data: overview, refresh } = useAsyncData<SubscriptionOverview | null>(
    'subscription-overview',
    async () => {
      const res = await graphql<{ data?: { subscriptionOverview?: SubscriptionOverview | null } }>(OVERVIEW_QUERY)
      return res?.data?.subscriptionOverview ?? null
    },
    { default: () => null },
  )

  return { overview, refresh }
}
