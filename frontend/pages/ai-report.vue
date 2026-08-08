<script setup lang="ts">
import Button from 'primevue/button'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}
const router = useRouter()

const loading = ref(false)
const report = ref<Record<string, unknown> | null>(null)
const error = ref('')

const generateReport = async () => {
  loading.value = true
  error.value = ''
  report.value = null
  try {
    const result = await $fetch<Record<string, unknown>>(
      `${config.public.apiBaseUrl}/ai/portfolio-report/`,
      {
        method: 'POST',
        headers,
      },
    )
    report.value = result
  } catch (e: unknown) {
    const err = e as { status?: number; message?: string }
    if (err.status === 401) {
      await router.push('/login')
    } else {
      error.value = err instanceof Error ? err.message : 'Erro ao gerar relatório.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Relatório de portfólio com IA</h1>
        <p class="mt-1 text-sepia-600">Análise personalizada do seu patrimônio com base nos dados reais.</p>
      </div>
      <Button
        :disabled="loading"
        class="!rounded-lg !bg-sepia-600 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-700 disabled:!opacity-50"
        @click="generateReport"
      >
        {{ loading ? 'Gerando...' : 'Gerar relatório' }}
      </Button>
    </div>

    <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

    <div v-if="report" class="rounded-xl border border-sepia-200 bg-white p-6 shadow-sm">
      <h3 class="mb-4 text-lg font-semibold text-sepia-900">Resultado da análise</h3>
      <pre class="whitespace-pre-wrap rounded-lg bg-sepia-50 p-4 text-sm text-sepia-700">{{ JSON.stringify(report, null, 2) }}</pre>
    </div>

    <div v-else class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:robot" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhum relatório gerado ainda.</p>
      <p class="mt-1 text-sm text-sepia-400">Clique em gerar para analisar seu portfólio.</p>
    </div>
  </section>
</template>
