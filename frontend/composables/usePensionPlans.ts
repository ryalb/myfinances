export type PensionPlan = {
  id: number
  name: string
  provider: string
  balance: number
  is_manual: boolean
}

export type PensionPlanInput = {
  name: string
  provider: string
  balance: number
}

export function usePensionPlans() {
  const { get, post, patch, del } = useApi()

  const { data: plans, refresh } = useAsyncData<PensionPlan[]>(
    'pension-plans',
    async () => (await get<PensionPlan[]>('/pension-plans/')) || [],
    { default: () => [] },
  )

  const createPlan = async (input: PensionPlanInput) => {
    await post('/pension-plans/', { ...input })
    await refresh()
  }

  const updatePlan = async (id: number, input: Partial<PensionPlanInput>) => {
    await patch(`/pension-plans/${id}/`, { ...input })
    await refresh()
  }

  const deletePlan = async (id: number) => {
    await del(`/pension-plans/${id}/`)
    await refresh()
  }

  return { plans, refresh, createPlan, updatePlan, deletePlan }
}
