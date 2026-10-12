import type { Ref } from 'vue'

export type CdiBenchmark = {
  as_of: string | null
  annual_rate: string | null
  m1: string | null
  m3: string | null
  m12: string | null
}

export type IpcaBenchmark = {
  as_of: string | null
  m1: string | null
  m3: string | null
  m12: string | null
}

export type MarketBenchmarks = {
  cdi: CdiBenchmark
  ipca: IpcaBenchmark
  cdi_since: { date: string; value: string | null }[]
}

export type BenchmarkWindow = 'm1' | 'm3' | 'm12'

const EMPTY: MarketBenchmarks = {
  cdi: { as_of: null, annual_rate: null, m1: null, m3: null, m12: null },
  ipca: { as_of: null, m1: null, m3: null, m12: null },
  cdi_since: [],
}

const toNumber = (v: string | null | undefined): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

// `sinceDates` sao as datas de compra da carteira: o backend devolve o CDI
// acumulado desde cada uma, a comparacao justa para "rendimento desde a compra".
export function useMarketBenchmarks(sinceDates: Ref<string[]>) {
  const { get } = useApi()

  const { data: benchmarks, refresh } = useAsyncData<MarketBenchmarks>(
    'market-benchmarks',
    async () => {
      const since = sinceDates.value.length ? `?since=${sinceDates.value.join(',')}` : ''
      return (await get<MarketBenchmarks>(`/market-benchmarks/${since}`)) || EMPTY
    },
    { default: () => EMPTY, watch: [sinceDates] },
  )

  const cdi = (window: BenchmarkWindow) => toNumber(benchmarks.value?.cdi[window])
  const ipca = (window: BenchmarkWindow) => toNumber(benchmarks.value?.ipca[window])
  const cdiAnnualRate = computed(() => toNumber(benchmarks.value?.cdi.annual_rate))

  const cdiSinceByDate = computed(() => {
    const byDate = new Map<string, number | null>()
    for (const row of benchmarks.value?.cdi_since || []) byDate.set(row.date, toNumber(row.value))
    return byDate
  })
  const cdiSince = (date: string | null) => (date ? cdiSinceByDate.value.get(date) ?? null : null)

  return { benchmarks, cdi, ipca, cdiAnnualRate, cdiSince, refresh }
}
