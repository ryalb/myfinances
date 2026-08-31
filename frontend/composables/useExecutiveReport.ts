export type ContributionPlanRow = {
  asset_class: string
  label: string
  target_percentage: number
  actual_percentage: number
  actual_amount: number
  suggested_amount: number
}

export type ExecutiveReport = {
  id: number
  contribution_amount: number
  contribution_plan: ContributionPlanRow[]
  summary: string
  goal_fit: string[]
  performance_verdict: string[]
  contribution_rationale: string[]
  disclaimer: string
  sources: { source_type: string, source_id: string, similarity: number }[]
  created_at: string
  // Só vem na resposta de geração (POST): estatística da indexação daquela
  // chamada, não faz parte do relatório persistido.
  index?: { indexed: number, skipped: number, removed: number }
}

export function useExecutiveReport() {
  const { get, post, del } = useApi()

  // Carrega o relatório já persistido (se existir) assim que a página monta --
  // "Reanalisar" substitui esse relatório, não empilha um novo.
  const { data: report, refresh } = useAsyncData<ExecutiveReport | null>(
    'executive-report',
    () => get<ExecutiveReport>('/ai/executive-report/'),
    { default: () => null },
  )

  const loading = ref(false)
  const error = ref('')

  const generate = async (contributionAmount?: number) => {
    loading.value = true
    error.value = ''
    try {
      const body = contributionAmount ? { contribution_amount: contributionAmount } : {}
      report.value = await post<ExecutiveReport>('/ai/executive-report/', body)
    } catch (e: unknown) {
      error.value = extractApiError(e, 'Erro ao gerar o relatório executivo.')
    } finally {
      loading.value = false
    }
  }

  const remove = async () => {
    await del('/ai/executive-report/')
    report.value = null
  }

  return { report, loading, error, generate, remove, refresh }
}
