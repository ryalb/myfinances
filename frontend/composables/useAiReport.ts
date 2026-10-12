export type ReportSource = {
  source_type: string
  source_id: string
  similarity: number
}

// Rótulos dos domínios que o backend indexa (source_type do DocumentChunk).
const SOURCE_LABELS: Record<string, string> = {
  financial_summary: 'Resumo patrimonial',
  accounts: 'Contas',
  cards: 'Cartões',
  investments: 'Investimentos',
  pension_plans: 'Previdência',
  goals: 'Metas',
  future_projection: 'Simulação de futuro financeiro',
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
