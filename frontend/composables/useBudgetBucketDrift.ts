export type BucketDriftRow = {
  bucket: string
  label: string
  targetPercentage: number
  actualPercentage: number
  actualAmount: number
  driftPp: number
}

export type OptimizerAccount = {
  id: number
  name: string
  type: string
}

type OptimizerData = {
  drift: BucketDriftRow[]
  accounts: OptimizerAccount[]
}

const OPTIMIZER_QUERY = `{
  budgetBucketDrift { bucket label targetPercentage actualPercentage actualAmount driftPp }
  accounts { id name type }
}`

const EMPTY: OptimizerData = { drift: [], accounts: [] }

export function useBudgetBucketDrift() {
  const { graphql } = useApi()

  // Mes atual, sempre -- o otimizador orienta a decisao de agora, nao navega
  // historico (isso ja existe na Revisao mensal). Uma so ida ao GraphQL: o
  // drift e a lista de contas para tagueamento saem juntos.
  const { data: optimizer, refresh } = useAsyncData<OptimizerData>(
    'budget-bucket-drift',
    async () => {
      const res = await graphql<{
        data?: { budgetBucketDrift?: BucketDriftRow[], accounts?: OptimizerAccount[] }
      }>(OPTIMIZER_QUERY)
      return {
        drift: res?.data?.budgetBucketDrift ?? [],
        accounts: res?.data?.accounts ?? [],
      }
    },
    { default: () => EMPTY },
  )

  return { optimizer, refresh }
}
