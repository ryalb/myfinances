export type BudgetBucketTarget = {
  id: number
  bucket: string
  target_percentage: number
  created_at: string
  updated_at: string
}

export type BudgetBucketTargetInput = {
  bucket: string
  target_percentage: number
}

// Rotulos em pt-BR dos buckets -- mesmo BudgetBucket.choices do backend
// (models.py), duplicado aqui porque o schema GraphQL/REST expõe só o value.
export const BUDGET_BUCKET_LABELS: Record<string, string> = {
  fixed_expenses: 'Despesas fixas',
  investments: 'Investimentos',
  emergency_fund: 'Reserva de emergência',
  goals: 'Metas',
  discretionary: 'Discricionário',
}

// Subconjunto de buckets que uma conta pode representar. `fixed_expenses` e
// `discretionary` vêm de categoria de transação (ver `budget_buckets.
// classify_transaction_bucket` no backend), não de conta tagueada -- oferecer
// esses dois no seletor de conta seria uma tag sem efeito nenhum no cálculo.
export const TAGGABLE_BUCKETS = ['investments', 'emergency_fund', 'goals'] as const

export function useBudgetBucketTargets() {
  const { get, put } = useApi()

  const { data: targets, refresh } = useAsyncData<BudgetBucketTarget[]>(
    'budget-bucket-targets',
    async () => (await get<BudgetBucketTarget[]>('/budget-bucket-targets/')) || [],
    { default: () => [] },
  )

  // Substitui o lote inteiro -- mesmo motivo de `usePortfolioTargets.saveTargets`
  // (a soma só faz sentido validada sobre o conjunto completo).
  const saveTargets = async (rows: BudgetBucketTargetInput[]) => {
    const saved = await put<BudgetBucketTarget[]>('/budget-bucket-targets/', rows)
    await refresh()
    return saved
  }

  return { targets, saveTargets, refresh }
}
