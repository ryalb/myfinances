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
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

  const now = new Date()
  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString()
  const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1).toISOString()

  const [accountsRes, transactionsRes, summaryRes] = await Promise.all([
    $fetch<{ balance: number; type: string; available_balance: number }[]>(`${config.public.apiBaseUrl}/accounts/`, {
      headers,
    }).catch(() => []),
    $fetch<{ amount: number; type: string; booked_at: string }[]>(`${config.public.apiBaseUrl}/transactions/?start_date=${currentMonthStart}&end_date=${nextMonthStart}`, {
      headers,
    }).catch(() => []),
    $fetch<{ assets: number; liabilities: number; net_worth: number; breakdown: Record<string, number> }>(
      `${config.public.apiBaseUrl}/summary/`,
      { headers },
    ).catch(() => null),
  ])

  const accounts = accountsRes as { balance: number; type: string; available_balance: number }[]
  const transactions = transactionsRes as { amount: number; type: string; booked_at: string }[]
  const summary = summaryRes as { assets: number; liabilities: number; net_worth: number; breakdown: Record<string, number> } | null

  const patrimonyTotal = summary?.assets || accounts.reduce((acc, account) => acc + Number(account.available_balance || account.balance || 0), 0)
  const netBalance = summary?.net_worth || patrimonyTotal
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
    assets: summary?.assets || 0,
    liabilities: summary?.liabilities || 0,
    breakdown: {
      cash: summary?.breakdown?.cash || 0,
      investments: summary?.breakdown?.investments || 0,
      pension: summary?.breakdown?.pension || 0,
      debts: summary?.breakdown?.debts || 0,
      creditCards: summary?.breakdown?.credit_cards || 0,
    },
  }
}
