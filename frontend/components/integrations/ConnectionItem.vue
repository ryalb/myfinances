<script setup lang="ts">
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

const statusColors: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  pending: 'bg-amber-100 text-amber-700',
  error: 'bg-rose-100 text-rose-700',
  expired: 'bg-slate-100 text-slate-600',
}

const sync = async () => {
  syncing.value = true
  try {
    await post(`/connections/${props.connection.id}/sync/`, { kind: 'incremental' })
  } finally {
    syncing.value = false
  }
}

const remove = async () => {
  if (!confirm('Tem certeza que deseja remover esta conexão?')) return
  removing.value = true
  try {
    await del(`/connections/${props.connection.id}/`)
    navigateTo('/integrations')
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <h4 class="font-semibold text-slate-900">{{ props.connection.institution.name }}</h4>
        <p class="mt-1 text-xs text-slate-500">Conectado em {{ new Date(props.connection.created_at).toLocaleDateString('pt-BR') }}</p>
      </div>
      <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusColors[props.connection.status] || 'bg-slate-100 text-slate-600']">
        {{ props.connection.status }}
      </span>
    </div>

    <!-- Last synced -->
    <div v-if="props.connection.last_synced_at" class="mt-3 text-xs text-slate-500">
      Última sincronização: {{ new Date(props.connection.last_synced_at).toLocaleString('pt-BR') }}
    </div>

    <!-- Error message -->
    <p v-if="props.connection.error_message" class="mt-2 text-xs text-rose-600">
      {{ props.connection.error_message }}
    </p>

    <!-- Actions -->
    <div class="mt-4 flex gap-2">
      <button
        :disabled="syncing"
        class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        @click="sync"
      >
        {{ syncing ? 'Sincronizando...' : 'Sincronizar agora' }}
      </button>
      <button
        :disabled="removing"
        class="rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
        @click="remove"
      >
        {{ removing ? 'Removendo...' : 'Remover' }}
      </button>
    </div>
  </div>
</template>
