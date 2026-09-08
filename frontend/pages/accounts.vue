<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: accounts } = await useFetch<
  {
    id: number
    name: string
    number: string
    type: string
    currency: string
    balance: number
    available_balance: number
    institution_name: string
    identity: {
      full_name: string
      document: string
      document_type: string
    } | null
  }[]
>(`${config.public.apiBaseUrl}/accounts/`, { key: 'accounts-page', headers })

const typeLabels: Record<string, string> = {
  checking: 'Conta Corrente',
  savings: 'Poupança',
  brokerage: 'Corretora',
  credit: 'Crédito',
  other: 'Outro',
}

const typeColors: Record<string, string> = {
  checking: 'bg-sepia-100 text-sepia-700',
  savings: 'bg-azul-100 text-azul-700',
  brokerage: 'bg-sepia-100 text-sepia-700',
  credit: 'bg-amber-100 text-amber-700',
  other: 'bg-sepia-100 text-sepia-600',
}

// Alguns bancos mandam `name` generico (igual ao label do tipo, ex. "Conta
// Corrente") pra toda conta desse tipo, sem apelido proprio -- nesse caso o
// nome da instituicao distingue melhor as contas do que repetir o tipo.
const displayName = (account: { name: string; type: string; institution_name: string }) => {
  const name = account.name?.trim()
  const genericLabel = typeLabels[account.type] || account.type
  if (!name || name === genericLabel) return account.institution_name || name || genericLabel
  return name
}

const uiStore = useUiStore()
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Contas</h1>

    <div v-if="!accounts?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:bank-off" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma conta encontrada.</p>
      <p class="mt-1 text-sm text-sepia-400">Conecte uma instituição para ver suas contas.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <article
        v-for="account in accounts"
        :key="account.id"
        class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm"
      >
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ displayName(account) }}</h3>
            <span :class="['mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium', typeColors[account.type] || typeColors.other]">
              {{ typeLabels[account.type] || account.type }}
            </span>
            <p v-if="account.number" class="mt-1 text-xs text-sepia-400">Conta: {{ account.number }}</p>
            <p v-if="account.identity?.full_name" class="mt-1 text-xs text-sepia-400">
              Titular: {{ account.identity.full_name }}
              <span v-if="account.identity.document">· {{ account.identity.document }}</span>
            </p>
          </div>
          <p :class="['text-right font-mono text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">{{ formatBRL(account.available_balance || account.balance) }}</p>
        </div>
        <p :class="['mt-2 text-xs text-sepia-400', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">Saldo disponível: {{ formatBRL(account.available_balance) }}</p>
      </article>
    </div>
  </section>
</template>
