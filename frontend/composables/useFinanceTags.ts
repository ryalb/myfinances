export type FinanceTag = {
  id: number
  kind: 'asset_class' | 'budget_bucket'
  value: string
  account: number | null
  investment: number | null
  goal: number | null
  created_at: string
  updated_at: string
}

export type FinanceTagInput = {
  kind: 'asset_class' | 'budget_bucket'
  value: string
  account?: number | null
  investment?: number | null
  goal?: number | null
}

// `kind` fixo por composable: cada tela do app trabalha com um domínio só
// (construtor de portfólio = asset_class; otimizador, na Fase 6 = budget_bucket).
export function useFinanceTags(kind: 'asset_class' | 'budget_bucket') {
  const { get, post, patch, del } = useApi()

  const { data: tags, refresh } = useAsyncData<FinanceTag[]>(
    `finance-tags-${kind}`,
    async () => (await get<FinanceTag[]>(`/finance-tags/?kind=${kind}`)) || [],
    { default: () => [] },
  )

  const createTag = async (input: Omit<FinanceTagInput, 'kind'>) => {
    await post('/finance-tags/', { ...input, kind })
    await refresh()
  }

  // Reclassificar uma conta/investimento já tagueado: PATCH no valor, não
  // apagar e recriar -- mesmo id, sem janela em que a conta fica sem tag.
  const updateTag = async (id: number, value: string) => {
    await patch(`/finance-tags/${id}/`, { value })
    await refresh()
  }

  const deleteTag = async (id: number) => {
    await del(`/finance-tags/${id}/`)
    await refresh()
  }

  return { tags, createTag, updateTag, deleteTag, refresh }
}
