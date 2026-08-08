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
  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString()
  const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1).toISOString()

  const [accountsRes, transactionsRes, summaryRes] = await Promise.all([
    get<{ balance: number; type: string; available_balance: number }[]>(`/accounts/`),
    get<{ amount: number; type: string; booked_at: string }[]>(`/transactions/?start_date=${currentMonthStart}&end_date=${nextMonthStart}`),
    get<{ assets: number; liabilities: number; net_worth: number; breakdown: Record<string, number> }>(`/summary/`),
  ])

  const accounts = accountsRes || []
  const transactions = transactionsRes || []
  const summary = summaryRes || null

  const patrimonyTotal = summary ? Number(summary.assets || 0) : accounts.reduce((acc, account) => acc + Number(account.available_balance || account.balance || 0), 0)
  const netBalance = summary ? Number(summary.net_worth || patrimonyTotal) : patrimonyTotal
  const monthlyExpenses = transactions
    .filter((tx) => tx.type === 'debit')
    .reduce((acc, tx) => acc + Number(tx.amount || 0), 0)
  const monthlyIncome = transactions
    .filter((tx) => tx.type === 'credit')
    .reduce((acc, tx) => acc + Number(tx.amount || 0), 0)
  const savingsRate = monthlyIncome > 0 ? ((monthlyIncome - monthlyExpenses) / monthlyIncome) * 100 : 0

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
