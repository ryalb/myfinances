export type CategorizationRule = {
  id: number
  pattern: string
  category: string
  priority: number
  is_active: boolean
}

export type CategorizationRuleInput = {
  pattern: string
  category: string
  priority: number
  is_active?: boolean
}

export function useCategorizationRules() {
  const { get, post, patch, del } = useApi()

  const { data: rules, refresh } = useAsyncData<CategorizationRule[]>(
    'categorization-rules',
    async () => (await get<CategorizationRule[]>('/categorization-rules/')) || [],
    { default: () => [] },
  )

  const createRule = async (input: CategorizationRuleInput) => {
    await post('/categorization-rules/', { ...input })
    await refresh()
  }

  const updateRule = async (id: number, input: Partial<CategorizationRuleInput>) => {
    await patch(`/categorization-rules/${id}/`, { ...input })
    await refresh()
  }

  const deleteRule = async (id: number) => {
    await del(`/categorization-rules/${id}/`)
    await refresh()
  }

  /**
   * Reaplica as regras ao histórico já importado e devolve quantos lançamentos
   * mudaram. Sem isso criar uma regra não tem efeito visível: o motor só roda no
   * momento da importação.
   */
  const reapply = async (): Promise<number> => {
    const result = await post<{ updated: number }>('/categorization-rules/reapply/', {})
    return result?.updated ?? 0
  }

  return { rules, refresh, createRule, updateRule, deleteRule, reapply }
}
