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
  const config = useRuntimeConfig()
  const router = useRouter()
  const { logout } = useAuth()

  const { data: overview, refresh } = useAsyncData<SubscriptionOverview | null>(
    'subscription-overview',
    async () => {
      try {
        const res = await $fetch<{ data?: { subscriptionOverview?: SubscriptionOverview | null } }>(
          `${config.public.graphqlEndpoint}`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${useCookie<string | null>('access_token').value}`,
              'Content-Type': 'application/json',
            },
            body: { query: OVERVIEW_QUERY },
          }
        )
        return res?.data?.subscriptionOverview ?? null
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

  return { overview, refresh }
}
