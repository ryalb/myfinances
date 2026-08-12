<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: cards } = await useFetch<
  {
    id: number
    name: string
    last4: string
    credit_limit: number
    current_balance: number
    due_day: number | null
    close_day: number | null
  }[]
>(`${config.public.apiBaseUrl}/cards/`, { key: 'cards-page', headers })

const uiStore = useUiStore()
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Cartões de crédito</h1>

    <div v-if="!cards?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:credit-card-off" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum cartão encontrado.</p>
      <p class="mt-1 text-sm text-sepia-400">Conecte uma instituição para ver seus cartões.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <article
        v-for="card in cards"
        :key="card.id"
        class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm"
      >
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ card.name }}</h3>
            <p class="mt-1 text-sm text-sepia-500">
              <span v-if="card.last4">**** {{ card.last4 }}</span>
              <span v-else>Sem final</span>
            </p>
          </div>
          <p :class="['text-right font-mono text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">{{ formatBRL(card.current_balance) }}</p>
        </div>
        <div class="mt-4 flex items-center justify-between text-sm text-sepia-600">
          <span :class="uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : ''">Limite: {{ formatBRL(card.credit_limit) }}</span>
          <span v-if="card.due_day">Vencimento: dia {{ card.due_day }}</span>
        </div>
      </article>
    </div>
  </section>
</template>
