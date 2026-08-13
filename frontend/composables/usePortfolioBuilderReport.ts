export type PortfolioBuilderDriftRow = {
  asset_class: string
  label: string
  target_percentage: number
  actual_percentage: number
  actual_amount: number
  drift_pp: number
}

export type PortfolioBuilderReport = {
  id: number
  drift: PortfolioBuilderDriftRow[]
  guidance: string
  rebalancing_actions: string[]
  common_mistakes: string[]
  disclaimer: string
  sources: { source_type: string, source_id: string, similarity: number }[]
  created_at: string
  // Só vem na resposta de geração (POST): estatística da indexação daquela
  // chamada, não faz parte do relatório persistido.
  index?: { indexed: number, skipped: number, removed: number }
}

export function usePortfolioBuilderReport() {
  const { get, post, del } = useApi()

  // Carrega a orientação já persistida (se existir) assim que a página monta --
  // "Reanalisar" substitui essa orientação, não empilha uma nova.
  const { data: report, refresh } = useAsyncData<PortfolioBuilderReport | null>(
    'portfolio-builder-report',
    () => get<PortfolioBuilderReport>('/ai/portfolio-builder/'),
    { default: () => null },
  )

  const loading = ref(false)
  const error = ref('')

  const generate = async () => {
    loading.value = true
    error.value = ''
    try {
      report.value = await post<PortfolioBuilderReport>('/ai/portfolio-builder/', {})
    } catch (e: unknown) {
      error.value = extractApiError(e, 'Erro ao gerar a orientação do portfólio.')
    } finally {
      loading.value = false
    }
  }

  const remove = async () => {
    await del('/ai/portfolio-builder/')
    report.value = null
  }

  return { report, loading, error, generate, remove, refresh }
}
