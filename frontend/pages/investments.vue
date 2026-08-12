<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: investments } = await useFetch<
  {
    id: number
    name: string
    kind: string
    currency: string
  }[]
>(`${config.public.apiBaseUrl}/investments/`, { key: 'investments-page', headers })

const { data: positions } = await useFetch<
  {
    id: number
    investment: number
    as_of_date: string
    quantity: number
    unit_price: number
    market_value: number
  }[]
>(`${config.public.apiBaseUrl}/investment-positions/`, { key: 'positions-page', headers })

const latestPositions = computed(() => {
  if (!positions.value?.length) return []
  const byInvestment = new Map<number, (typeof positions.value)[0]>()
  for (const p of positions.value) {
    const current = byInvestment.get(p.investment)
    if (!current || new Date(p.as_of_date) > new Date(current.as_of_date)) {
      byInvestment.set(p.investment, p)
    }
  }
  return Array.from(byInvestment.values())
})

const uiStore = useUiStore()
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Investimentos</h1>

    <div v-if="!investments?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:chart-line" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum investimento encontrado.</p>
      <p class="mt-1 text-sm text-sepia-400">Conecte uma instituição para ver seus investimentos.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <article
        v-for="investment in investments"
        :key="investment.id"
        class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm"
      >
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ investment.name }}</h3>
            <span class="mt-1 inline-block rounded-full bg-sepia-100 px-2 py-0.5 text-xs font-medium text-sepia-700">
              {{ investment.kind }}
            </span>
          </div>
          <p :class="['text-right font-mono text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">
            {{
              formatBRL(
                latestPositions.find(p => p.investment === investment.id)?.market_value || 0
              )
            }}
          </p>
        </div>
      </article>
    </div>
  </section>
</template>
