<script setup lang="ts">
import Button from 'primevue/button'
import { extractApiError } from '@/composables/useApi'
import { formatIsoDateOnly, formatIsoDateTime } from '@/composables/useDateFormat'
const props = defineProps<{
  connection: {
    id: number
    institution: { name: string }
    external_id: string
    status: string
    last_synced_at: string | null
    error_message: string
    created_at: string
  }
}>()

const { post, del } = useApi()
const syncing = ref(false)
const removing = ref(false)
const error = ref('')
const lastSyncEvent = useSyncEvent()
let syncTimeout: ReturnType<typeof setTimeout> | null = null

const statusColors: Record<string, string> = {
  active: 'bg-azul-100 text-azul-700',
  pending: 'bg-amber-100 text-amber-700',
  error: 'bg-vermelho-100 text-vermelho-700',
  expired: 'bg-sepia-100 text-sepia-600',
}

const sync = async () => {
  syncing.value = true
  error.value = ''
  try {
    await post(`/connections/${props.connection.id}/sync/`, { kind: 'incremental' })
    // O POST so enfileira o job no Celery; a sincronizacao real termina depois,
    // avisada pelo evento `sync_event` no WebSocket. Sem o timeout, perder esse
    // evento (WS caiu, reconectando) deixa o botao girando pra sempre.
    if (syncTimeout) clearTimeout(syncTimeout)
    syncTimeout = setTimeout(() => {
      syncing.value = false
    }, 60_000)
  } catch (e: unknown) {
    syncing.value = false
    error.value = extractApiError(e, 'Erro ao sincronizar a conexão.')
  }
}

watch(lastSyncEvent, (event) => {
  if (!event || event.connectionId !== props.connection.id) return
  if (event.status === 'SUCCESS' || event.status === 'FAILED') {
    if (syncTimeout) {
      clearTimeout(syncTimeout)
      syncTimeout = null
    }
    syncing.value = false
  }
})

onUnmounted(() => {
  if (syncTimeout) clearTimeout(syncTimeout)
})

const remove = async () => {
  if (!confirm('Tem certeza que deseja remover esta conexão?')) return
  removing.value = true
  error.value = ''
  try {
    await del(`/connections/${props.connection.id}/`)
    // Navega só depois do sucesso: antes uma remoção falha saía da tela como se
    // tivesse funcionado, e a conexão reaparecia no próximo carregamento.
    navigateTo('/integrations')
  } catch (e: unknown) {
    error.value = extractApiError(e, 'Erro ao remover a conexão.')
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <h3 class="font-semibold text-sepia-900">{{ props.connection.institution.name }}</h3>
        <p class="mt-1 text-xs text-sepia-500">Conectado em {{ formatIsoDateOnly(props.connection.created_at) }}</p>
      </div>
      <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusColors[props.connection.status] || 'bg-sepia-100 text-sepia-600']">
        {{ props.connection.status }}
      </span>
    </div>

    <!-- Last synced -->
    <div v-if="props.connection.last_synced_at" class="mt-3 text-xs text-sepia-500">
      Última sincronização: {{ formatIsoDateTime(props.connection.last_synced_at) }}
    </div>

    <!-- Error message -->
    <p v-if="props.connection.error_message" class="mt-2 text-xs text-vermelho-600">
      {{ props.connection.error_message }}
    </p>

    <!-- Falha da última ação nesta conexão (sync/remoção) -->
    <p v-if="error" class="mt-2 text-xs text-vermelho-600">{{ error }}</p>

    <!-- Actions -->
    <div class="mt-4 flex gap-2">
      <Button
        :disabled="syncing"
        class="!flex !items-center !gap-1.5 !rounded-lg !bg-sepia-900 !px-3 !py-1.5 !text-xs !font-medium !text-white !whitespace-nowrap hover:!bg-sepia-950 disabled:!opacity-50"
        @click="sync"
      >
        <Icon v-if="syncing" icon="mdi:loading" class="h-3.5 w-3.5 animate-spin" />
        {{ syncing ? 'Sincronizando...' : 'Sincronizar agora' }}
      </Button>
      <Button
        :disabled="removing"
        class="!rounded-lg !bg-vermelho-600 !px-3 !py-1.5 !text-xs !font-medium !text-white !whitespace-nowrap hover:!bg-vermelho-700 disabled:!opacity-50"
        @click="remove"
      >
        {{ removing ? 'Removendo...' : 'Remover' }}
      </Button>
    </div>
  </div>
</template>
