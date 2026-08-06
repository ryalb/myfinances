<script setup lang="ts">
const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: institutions, refresh: refreshInstitutions } = await useFetch<
  { id: number; name: string; provider_id: string; logo_url: string }[]
>(`${config.public.apiBaseUrl}/institutions/`, {
  headers,
  default: () => [],
})

const { data: connections } = await useFetch<
  {
    id: number
    institution: { name: string }
    external_id: string
    status: string
    last_synced_at: string | null
    error_message: string
    created_at: string
  }
>(`${config.public.apiBaseUrl}/connections/`, { key: 'connections', headers })
</script>

<template>
  <section class="space-y-8">
    <div>
      <h1 class="text-2xl font-semibold">Integrações financeiras</h1>
      <p class="mt-1 text-slate-600">Conecte suas instituições para importar dados automaticamente via Pluggy.</p>
    </div>

    <!-- Existing connections -->
    <div v-if="connections?.length" class="space-y-4">
      <h2 class="text-lg font-semibold text-slate-900">Conexões ativas</h2>
      <div class="grid gap-4 md:grid-cols-2">
        <integrations-connection-item v-for="conn in connections" :key="conn.id" :connection="conn" />
      </div>
    </div>

    <!-- Available institutions -->
    <div class="space-y-4">
      <h2 class="text-lg font-semibold text-slate-900">Instituições disponíveis</h2>
      <div class="space-y-2">
        <integrations-institution-item
          v-for="inst in institutions"
          :key="inst.id"
          :institution="inst"
          @connected="refreshInstitutions"
        />
        <p v-if="!institutions?.length" class="py-4 text-sm text-slate-500">Nenhuma instituição encontrada.</p>
      </div>
    </div>

    <!-- Sync history -->
    <div class="space-y-4">
      <h2 class="text-lg font-semibold text-slate-900">Histórico de sincronizações</h2>
      <integrations-sync-jobs-table />
    </div>
  </section>
</template>
