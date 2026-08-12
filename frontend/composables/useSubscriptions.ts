export type MatchedTransaction = {
  id: number
  description: string
  amount: number
  booked_at: string
  account_name: string | null
}

export type SubscriptionPayment = {
  id: number
  due_date: string
  paid_date: string | null
  status: string
  paid_amount: number | null
  matched_transaction: MatchedTransaction | null
}

export type Subscription = {
  id: number
  name: string
  category: string
  amount: number
  due_day: number
  is_active: boolean
  connection: number | null
  payment_account: number | null
  payments: SubscriptionPayment[]
}

export type SubscriptionInput = {
  name: string
  category: string
  amount: number
  due_day: number
  is_active?: boolean
  payment_account?: number | null
}

// `new Date().toISOString()` devolve a data em UTC: às 21h em São Paulo isso já é
// o dia seguinte, e o pagamento seria marcado como pago amanhã.
export function todayLocalISO(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export function useSubscriptions() {
  const { get, post, patch, del } = useApi()

  const { data: subscriptions, refresh } = useAsyncData<Subscription[]>(
    'subscriptions',
    async () => (await get<Subscription[]>('/subscriptions/')) || [],
    { default: () => [] },
  )

  const createSubscription = async (input: SubscriptionInput) => {
    await post('/subscriptions/', { ...input })
    await refresh()
  }

  const updateSubscription = async (id: number, input: Partial<SubscriptionInput>) => {
    await patch(`/subscriptions/${id}/`, { ...input })
    await refresh()
  }

  const deleteSubscription = async (id: number) => {
    await del(`/subscriptions/${id}/`)
    await refresh()
  }

  const reconcileSubscriptions = async () => {
    await post('/subscriptions/reconcile/', {})
    await refresh()
  }

  /** Marca o pagamento como pago. `amount` ausente cai no valor esperado da
   * assinatura, que é o caso comum de marcação manual. */
  const markPaid = async (paymentId: number, options: { amount?: number; paidDate?: string } = {}) => {
    await patch(`/subscription-payments/${paymentId}/`, {
      status: 'paid',
      paid_date: options.paidDate || todayLocalISO(),
      ...(options.amount === undefined ? {} : { paid_amount: options.amount }),
    })
    await refresh()
  }

  /** Desfaz a marcação. Limpa data e valor junto: um pagamento pendente com
   * `paid_date` preenchido apareceria como pago em qualquer leitura futura. */
  const markPending = async (paymentId: number) => {
    await patch(`/subscription-payments/${paymentId}/`, {
      status: 'pending',
      paid_date: null,
      paid_amount: null,
    })
    await refresh()
  }

  return {
    subscriptions,
    refresh,
    createSubscription,
    updateSubscription,
    deleteSubscription,
    reconcileSubscriptions,
    markPaid,
    markPending,
  }
}
