export function useGoals() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

  const { data: goals, refresh } = useState<{
    id: number
    name: string
    target_amount: number
    current_amount: number
    target_date: string | null
    status: string
    progress_percentage: number
    created_at: string
    updated_at: string
  }[]>('goals', async () => {
    try {
      return await $fetch(`${config.public.apiBaseUrl}/goals/`, { headers })
    } catch {
      return []
    }
  })

  const createGoal = async (goal: {
    name: string
    target_amount: number
    current_amount?: number
    target_date?: string
  }) => {
    await $fetch(`${config.public.apiBaseUrl}/goals/`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(goal),
    })
    await refresh()
  }

  const updateGoal = async (id: number, goal: Partial<typeof goal>) => {
    await $fetch(`${config.public.apiBaseUrl}/goals/${id}/`, {
      method: 'PATCH',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(goal),
    })
    await refresh()
  }

  const deleteGoal = async (id: number) => {
    await $fetch(`${config.public.apiBaseUrl}/goals/${id}/`, {
      method: 'DELETE',
      headers,
    })
    await refresh()
  }

  return { goals, createGoal, updateGoal, deleteGoal, refresh }
}
