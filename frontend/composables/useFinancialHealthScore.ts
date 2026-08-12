export type HealthScoreComponent = {
  key: string
  label: string
  score: number
  weight: number
  detail: string
}

export type FinancialHealthScore = {
  score: number
  components: HealthScoreComponent[]
  topActions: string[]
}

const HEALTH_SCORE_QUERY = `{
  financialHealthScore {
    score
    components { key label score weight detail }
    topActions
  }
}`

export function useFinancialHealthScore() {
  const { graphql } = useApi()

  const { data: healthScore, refresh } = useAsyncData<FinancialHealthScore | null>(
    'financial-health-score',
    async () => {
      const res = await graphql<{ data?: { financialHealthScore?: FinancialHealthScore | null } }>(HEALTH_SCORE_QUERY)
      return res?.data?.financialHealthScore ?? null
    },
    { default: () => null },
  )

  return { healthScore, refresh }
}
