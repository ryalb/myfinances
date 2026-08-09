<script setup lang="ts">
import Button from 'primevue/button'
import { useApi } from '~/composables/useApi'

definePageMeta({
  middleware: 'auth',
})

const config = useRuntimeConfig()
const api = useApi()

const { data: connections, refresh: refreshConnections } = await useFetch<
  {
    id: number
    institution: { name: string }
    external_id: string
    status: string
    last_synced_at: string | null
    error_message: string
    created_at: string
  }
>(`${config.public.apiBaseUrl}/connections/`, { key: 'connections', headers: api.getHeaders() })

const importing = ref(false)
const importError = ref('')
const importItemId = ref('')
const importMessage = ref('')

const regenerating = ref(false)
const regenerateError = ref('')
const regenerateSuccess = ref('')

const importItem = async () => {
  const itemId = importItemId.value.trim()
  if (!itemId) {
    importError.value = 'Informe o itemId do Dashboard da Pluggy.'
    return
  }
  importing.value = true
  importError.value = ''
  importMessage.value = ''
  try {
    const result = await api.post<{
      external_id: string
      status: string
      created: boolean
      item_status: string
      message?: string
      error?: string
    }>(`/pluggy/items/`, { itemId })
    if (result?.error) {
      importError.value = result.error
    } else {
      importMessage.value = result?.message || 'Item importado.'
      importItemId.value = ''
    }
    await refreshConnections()
  } catch (error: unknown) {
    importError.value =
      (error as { data?: { error?: string } } | null)?.data?.error ||
      (error as { message?: string } | null)?.message ||
      'Erro ao importar o item.'
  } finally {
    importing.value = false
  }
}

const regenerateAuth = async () => {
  regenerating.value = true
  regenerateError.value = ''
  regenerateSuccess.value = ''
  try {
    const result = await api.post<{ status: string; message?: string; error?: string }>(
      `/pluggy/regenerate-auth/`,
      {},
    )
    if (result?.error) {
      regenerateError.value = result.error
    } else {
      regenerateSuccess.value = result?.message || 'Autenticação do Pluggy revalidada.'
    }
  } catch (error: unknown) {
    const message =
      (error as { data?: { error?: string } } | null)?.data?.error ||
      (error as { message?: string } | null)?.message ||
      'Erro ao revalidar a autenticação.'
    regenerateError.value = message
  } finally {
    regenerating.value = false
  }
}
</script>

<template>
  <section class="space-y-8">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold">Integrações financeiras</h1>
          <p class="mt-1 text-sepia-600">Conecte suas instituições para importar dados automaticamente via Pluggy.</p>
        </div>
        <div class="flex gap-2">
          <Button
            class="!rounded-lg !border !border-sepia-200 !bg-white !px-3 !py-1.5 !text-xs !font-medium !text-sepia-600 hover:!bg-sepia-50"
            :disabled="regenerating"
            @click="regenerateAuth"
          >
            {{ regenerating ? 'Revalidando...' : 'Revalidar autenticação' }}
          </Button>
        </div>
      </div>

      <p v-if="regenerateSuccess" class="text-sm text-emerald-600">{{ regenerateSuccess }}</p>
      <p v-if="regenerateError" class="text-sm text-rose-600">{{ regenerateError }}</p>

    <!-- Import an item by id -->
    <div class="rounded-xl border border-sepia-200 bg-white p-4 shadow-sm">
      <label for="item-id" class="block text-sm font-medium text-sepia-700">Importar item da Pluggy</label>
      <p class="mt-1 text-xs text-sepia-500">
        Cole o <code class="rounded bg-sepia-100 px-1 py-0.5">itemId</code> que aparece no
        <a href="https://dashboard.pluggy.ai" target="_blank" class="text-sepia-500 underline">Dashboard da Pluggy</a>,
        em <strong>Itens Conectados</strong>, acima do nome do conector.
        Cada conexão do Meu Pluggy é um item separado — importe um por vez.
      </p>
      <div class="mt-2 flex gap-2">
        <input
          id="item-id"
          v-model="importItemId"
          type="text"
          placeholder="05187d4e-9824-45d5-af32-85c3fc1e1abd"
          class="w-full rounded-lg border border-sepia-200 bg-white px-3 py-1.5 font-mono text-sm text-sepia-800 placeholder:text-sepia-400 focus:border-sepia-300 focus:outline-none focus:ring-2 focus:ring-sepia-500/10"
          @keyup.enter="importItem"
        >
        <Button
          class="!rounded-lg !border !border-sepia-200 !bg-white !px-3 !py-1.5 !text-xs !font-medium !text-sepia-600 hover:!bg-sepia-50"
          :disabled="importing"
          @click="importItem"
        >
          {{ importing ? 'Importando...' : 'Importar' }}
        </Button>
      </div>
    </div>

    <p v-if="importMessage" class="text-sm text-emerald-600">{{ importMessage }}</p>
    <p v-if="importError" class="text-sm text-rose-600">{{ importError }}</p>

    <!-- Existing connections -->
    <div v-if="connections?.length" class="space-y-4">
      <h2 class="text-lg font-semibold text-sepia-900">Conexões ativas</h2>
      <div class="grid gap-4 md:grid-cols-2">
        <integrations-connection-item v-for="conn in connections" :key="conn.id" :connection="conn" />
      </div>
    </div>

    <!-- Meu Pluggy instructions -->
    <div class="rounded-xl border border-sepia-200 bg-white p-6 shadow-sm">
      <h2 class="text-lg font-semibold text-sepia-900">Conecte suas contas via Meu Pluggy</h2>
      <p class="mt-2 text-sm text-sepia-600">
        Para uso pessoal gratuito, utilize o <a href="https://meu.pluggy.ai" target="_blank" class="text-sepia-500 underline">Meu Pluggy</a>:
      </p>
      <ol class="mt-3 list-inside list-decimal space-y-1 text-sm text-sepia-600">
        <li>Crie sua conta em <a href="https://meu.pluggy.ai" target="_blank" class="text-sepia-500 underline">meu.pluggy.ai</a> e conecte seus bancos.</li>
        <li>No <a href="https://dashboard.pluggy.ai" target="_blank" class="text-sepia-500 underline">Dashboard da Pluggy</a>, clique em <strong>Conectar Conta</strong> → MeuPluggy e autorize <strong>uma</strong> conexão. Repita para cada banco: a tela de consentimento aceita uma conexão por autorização.</li>
        <li>Copie o <code class="rounded bg-sepia-100 px-1 py-0.5">itemId</code> de cada item e importe acima.</li>
      </ol>
      <p class="mt-3 text-xs text-sepia-500">
        Uso pessoal, gratuito e sem prazo de expiração. Consulte os <a href="https://www.pluggy.ai/precos" target="_blank" class="text-sepia-500 underline">planos</a> para uso comercial.
      </p>
    </div>

    <!-- Sync history -->
    <div class="space-y-4">
      <h2 class="text-lg font-semibold text-sepia-900">Histórico de sincronizações</h2>
      <integrations-sync-jobs-table />
    </div>
  </section>
</template>
