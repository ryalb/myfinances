<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import { formatBRL } from '@/composables/useCurrency'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: plans } = await useFetch<
  {
    id: number
    name: string
    provider: string
    balance: number
  }[]
>(`${config.public.apiBaseUrl}/pension-plans/`, { key: 'pension-page', headers })

const uiStore = useUiStore()
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-2xl font-semibold">Previdência privada</h1>

    <div v-if="!plans?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:shield-account" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum plano de previdência encontrado.</p>
      <p class="mt-1 text-sm text-sepia-400">Conecte uma instituição para ver seus planos.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <article
        v-for="plan in plans"
        :key="plan.id"
        class="rounded-xl border border-sepia-200 bg-white p-5 shadow-sm"
      >
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-sepia-900">{{ plan.name }}</h3>
            <p class="mt-1 text-sm text-sepia-500">{{ plan.provider }}</p>
          </div>
          <p :class="['text-right text-lg font-bold text-sepia-900', uiStore.isFinancialValueBlurred ? 'blur-sm select-none' : '']">{{ formatBRL(plan.balance) }}</p>
        </div>
      </article>
    </div>
  </section>
</template>
