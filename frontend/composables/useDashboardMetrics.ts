type DashboardMetrics = {
  patrimonyTotal: number
  netBalance: number
  monthlyExpenses: number
  monthlyIncome: number
  savingsRate: number
  assets: number
  liabilities: number
  breakdown: {
    cash: number
    investments: number
    pension: number
    debts: number
    creditCards: number
  }
}

export const useDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const { get } = useApi()

  const now = new Date()

  // Receita e despesa do mês vêm de `/cash-flow/`, não de somar `/transactions/`
  // no cliente. Três motivos:
  //
  // 1. `/transactions/` é paginado — somar `.results` daria só os 100 primeiros
  //    lançamentos do mês, errado em silêncio num mês movimentado.
  // 2. O backend agrega no banco, em vez de trafegar o mês inteiro para descartar.
  // 3. É a mesma fonte do gráfico de fluxo de caixa. Antes os cards e o gráfico
  //    podiam divergir, porque a soma no cliente ignorava as assinaturas.
  const [accountsRes, cashFlowRes, summaryRes] = await Promise.all([
    get<{ balance: number; type: string; available_balance: number }[]>(`/accounts/`),
    // `DecimalField` do DRF serializa como string por padrão, então estes campos
    // chegam como "5000.00" e não 5000. O `Number()` abaixo é obrigatório.
    get<{ income: string; expenses: string; savings: string; savings_rate: string }>(
      `/cash-flow/?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
    ),
    get<{ assets: number; liabilities: number; net_worth: number; breakdown: Record<string, number> }>(`/summary/`),
  ])

  const accounts = accountsRes || []
  const summary = summaryRes || null

  const patrimonyTotal = summary ? Number(summary.assets || 0) : accounts.reduce((acc, account) => acc + Number(account.available_balance || account.balance || 0), 0)
  const netBalance = summary ? Number(summary.net_worth || patrimonyTotal) : patrimonyTotal
  const monthlyExpenses = Number(cashFlowRes?.expenses || 0)
  const monthlyIncome = Number(cashFlowRes?.income || 0)
  const savingsRate = Number(cashFlowRes?.savings_rate || 0)

  return {
    patrimonyTotal,
    netBalance,
    monthlyExpenses,
    monthlyIncome,
    savingsRate,
    assets: Number(summary?.assets || 0),
    liabilities: Number(summary?.liabilities || 0),
    breakdown: {
      cash: Number(summary?.breakdown?.cash || 0),
      investments: Number(summary?.breakdown?.investments || 0),
      pension: Number(summary?.breakdown?.pension || 0),
      debts: Number(summary?.breakdown?.debts || 0),
      creditCards: Number(summary?.breakdown?.credit_cards || 0),
    },
  }
}
