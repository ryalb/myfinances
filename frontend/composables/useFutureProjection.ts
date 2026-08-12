export type ScenarioValue = {
  years: number
  netWorth: number
}

export type ScenarioSeries = {
  name: 'conservative' | 'base' | 'aggressive'
  values: ScenarioValue[]
}

export type LeveragePoint = {
  key: string
  label: string
  projectedNetWorth: number
  impact: number
}

export type GoalViability = {
  id: number
  name: string
  targetAmount: number
  targetDate: string | null
  onTrack: boolean
  shortfall: number
  projectedGrowth: number
  remainingNeeded: number
}

export type FutureProjection = {
  currentNetWorth: number
  monthlyContribution: number
  horizons: number[]
  scenarios: ScenarioSeries[]
  stress: ScenarioValue[]
  leveragePoints: LeveragePoint[]
  goals: GoalViability[]
}

const PROJECTION_QUERY = `{
  futureProjection {
    currentNetWorth
    monthlyContribution
    horizons
    scenarios { name values { years netWorth } }
    stress { years netWorth }
    leveragePoints { key label projectedNetWorth impact }
    goals { id name targetAmount targetDate onTrack shortfall projectedGrowth remainingNeeded }
  }
}`

// Rotulos em pt-BR dos nomes de cenario que vem do backend -- usados pelo
// gráfico e pelos cards da pagina do simulador.
export const SCENARIO_LABELS: Record<string, string> = {
  conservative: 'Conservador',
  base: 'Base',
  aggressive: 'Agressivo',
}

export function useFutureProjection() {
  const { graphql } = useApi()

  const { data: projection, refresh } = useAsyncData<FutureProjection | null>(
    'future-projection',
    async () => {
      const res = await graphql<{ data?: { futureProjection?: FutureProjection | null } }>(PROJECTION_QUERY)
      return res?.data?.futureProjection ?? null
    },
    { default: () => null },
  )

  return { projection, refresh }
}
