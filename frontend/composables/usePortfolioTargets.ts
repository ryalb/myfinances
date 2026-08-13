export type PortfolioTarget = {
  id: number
  asset_class: string
  target_percentage: number
  created_at: string
  updated_at: string
}

export type PortfolioTargetInput = {
  asset_class: string
  target_percentage: number
}

// Rotulos em pt-BR das classes de ativo -- mesmo AssetClass.choices do backend
// (models.py), duplicado aqui porque o schema GraphQL/REST expõe só o value.
export const ASSET_CLASS_LABELS: Record<string, string> = {
  fixed_income: 'Renda fixa',
  equity_br: 'Ações Brasil',
  equity_intl: 'Ações internacional',
  cash_reserve: 'Reserva de caixa',
  pension: 'Previdência',
}

export function usePortfolioTargets() {
  const { get, put } = useApi()

  const { data: targets, refresh } = useAsyncData<PortfolioTarget[]>(
    'portfolio-targets',
    async () => (await get<PortfolioTarget[]>('/portfolio-targets/')) || [],
    { default: () => [] },
  )

  // Substitui o lote inteiro -- não há CRUD por linha, ver
  // `PortfolioTargetsAPIView` no backend (a soma só faz sentido validada
  // sobre o conjunto completo).
  const saveTargets = async (rows: PortfolioTargetInput[]) => {
    const saved = await put<PortfolioTarget[]>('/portfolio-targets/', rows)
    await refresh()
    return saved
  }

  return { targets, saveTargets, refresh }
}
