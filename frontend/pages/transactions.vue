<script setup lang="ts">
const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: transactions } = await useFetch<
  {
    id: number
    description: string
    amount: number
    type: string
    category: string
    booked_at: string
  }[]
>(`${config.public.apiBaseUrl}/transactions/`, { key: 'transactions-page', headers })

const formatBRL = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

const typeBadge = (type: string) =>
  type === 'credit'
    ? 'bg-emerald-100 text-emerald-700'
    : 'bg-rose-100 text-rose-700'

const typeLabel = (type: string) => (type === 'credit' ? 'Receita' : 'Despesa')
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Transações</h1>

    <div v-if="!transactions?.length" class="rounded-lg border border-dashed border-slate-300 p-8 text-center">
      <Icon icon="mdi:receipt-outline" class="mx-auto mb-3 h-10 w-10 text-slate-300" />
      <p class="text-slate-500">Nenhuma transação encontrada.</p>
      <p class="mt-1 text-sm text-slate-400">Sincronize suas contas para ver as transações.</p>
    </div>

    <div v-else class="rounded-xl border border-slate-200 bg-white shadow-sm">
      <table class="w-full text-sm">
        <thead class="border-b border-slate-200 bg-slate-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Data</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Descrição</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Categoria</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Tipo</th>
            <th class="px-4 py-3 text-right font-medium text-slate-600">Valor</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tx in transactions.slice(0, 100)" :key="tx.id" class="border-b border-slate-100 last:border-0">
            <td class="px-4 py-3 text-slate-500">{{ new Date(tx.booked_at).toLocaleDateString('pt-BR') }}</td>
            <td class="px-4 py-3 font-medium text-slate-900">{{ tx.description }}</td>
            <td class="px-4 py-3">
              <span v-if="tx.category" class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {{ tx.category }}
              </span>
              <span v-else class="text-slate-400">—</span>
            </td>
            <td class="px-4 py-3">
              <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', typeBadge(tx.type)]">
                {{ typeLabel(tx.type) }}
              </span>
            </td>
            <td :class="['px-4 py-3 text-right font-medium', tx.type === 'credit' ? 'text-emerald-600' : 'text-rose-600']">
              {{ tx.type === 'credit' ? '+' : '-' }}{{ formatBRL(tx.amount) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
