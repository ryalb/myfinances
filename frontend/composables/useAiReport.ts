export type ReportSource = {
  source_type: string
  source_id: string
  similarity: number
}

export type PortfolioReport = {
  id: number
  query: string
  summary: string
  projections: string
  strengths: string[]
  weaknesses: string[]
  adjustments: string[]
  suggestions: string[]
  disclaimer: string
  sources: ReportSource[]
  created_at: string
  // Só vem na resposta de geração (POST): estatística da indexação daquela
  // chamada, não faz parte do relatório persistido.
  index?: { indexed: number; skipped: number; removed: number }
}

// Rótulos dos domínios que o backend indexa (source_type do DocumentChunk).
const SOURCE_LABELS: Record<string, string> = {
  financial_summary: 'Resumo patrimonial',
  accounts: 'Contas',
  cards: 'Cartões',
  investments: 'Investimentos',
  pension_plans: 'Previdência',
  goals: 'Metas',
  subscriptions: 'Assinaturas',
  categorization_rules: 'Regras de categorização',
  sync_history: 'Histórico de sincronização',
  transactions: 'Transações',
}

export function sourceLabel(source: ReportSource): string {
  const base = SOURCE_LABELS[source.source_type] || source.source_type
  // Transações são indexadas uma por mês, então o id é "2026-08" e diz algo ao
  // usuário. Nos outros domínios o id é o pk do usuário e só seria ruído.
  return source.source_type === 'transactions' ? `${base} · ${source.source_id}` : base
}

export function useAiReport() {
  const { post } = useApi()

  const report = ref<PortfolioReport | null>(null)
  const loading = ref(false)
  const error = ref('')

  const generate = async (query?: string) => {
    loading.value = true
    error.value = ''
    report.value = null
    try {
      const body = query?.trim() ? { query: query.trim() } : {}
      report.value = await post<PortfolioReport>('/ai/portfolio-report/', body)
    } catch (e: unknown) {
      error.value = extractApiError(e, 'Erro ao gerar o relatório.')
    } finally {
      loading.value = false
    }
  }

  // Mostra um relatório já persistido (histórico) sem chamar a LLM de novo.
  const view = (saved: PortfolioReport) => {
    error.value = ''
    report.value = saved
  }

  return { report, loading, error, generate, view }
}
