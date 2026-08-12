export type FutureProjectionReport = {
  id: number
  projection: {
    current_net_worth: number
    monthly_contribution: number
    horizons: number[]
    scenarios: Record<string, Record<string, number>>
    stress: Record<string, number>
    leverage_points: { key: string, label: string, projected_net_worth: number, impact: number }[]
    goals: {
      id: number
      name: string
      target_amount: number
      target_date: string | null
      on_track: boolean
      shortfall: number
      projected_growth: number
      remaining_needed: number
    }[]
  }
  narrative: string
  leverage_explanation: string[]
  goal_commentary: string[]
  disclaimer: string
  sources: { source_type: string, source_id: string, similarity: number }[]
  created_at: string
  // Só vem na resposta de geração (POST): estatística da indexação daquela
  // chamada, não faz parte do relatório persistido.
  index?: { indexed: number, skipped: number, removed: number }
}

export function useFutureProjectionReport() {
  const { get, post, del } = useApi()

  // Carrega a narração já persistida (se existir) assim que a página monta --
  // "Reanalisar" substitui essa narração, não empilha uma nova.
  const { data: report, refresh } = useAsyncData<FutureProjectionReport | null>(
    'future-projection-report',
    () => get<FutureProjectionReport>('/ai/future-projection/'),
    { default: () => null },
  )

  const loading = ref(false)
  const error = ref('')

  const generate = async () => {
    loading.value = true
    error.value = ''
    try {
      report.value = await post<FutureProjectionReport>('/ai/future-projection/', {})
    } catch (e: unknown) {
      error.value = extractApiError(e, 'Erro ao gerar a narração da simulação.')
    } finally {
      loading.value = false
    }
  }

  const remove = async () => {
    await del('/ai/future-projection/')
    report.value = null
  }

  return { report, loading, error, generate, remove, refresh }
}
