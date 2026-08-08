export function useGoals() {
  const { get, post, patch, del } = useApi()

  const { data: goals, refresh } = useAsyncData(
    'goals',
    async () => {
      return await get<{ id: number; name: string; target_amount: number; current_amount: number; target_date?: string }[]>(`/goals/`) || []
    },
    { default: () => [] },
  )

  const createGoal = async (goal: {
    name: string
    target_amount: number
    current_amount?: number
    target_date?: string
  }) => {
    await post(`/goals/`, goal)
    await refresh()
  }

  const updateGoal = async (id: number, goal: Partial<{ name: string; target_amount: number; current_amount: number; target_date?: string }>) => {
    await patch(`/goals/${id}/`, goal)
    await refresh()
  }

  const deleteGoal = async (id: number) => {
    await del(`/goals/${id}/`)
    await refresh()
  }

  return { goals, createGoal, updateGoal, deleteGoal, refresh }
}
