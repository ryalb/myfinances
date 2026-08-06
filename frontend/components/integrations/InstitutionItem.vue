<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  institution: { id: number; name: string; provider_id: string; logo_url: string }
}>()

const emit = defineEmits(['connected'])
const { post } = useApi()

const connecting = ref(false)
const error = ref('')

const connect = async () => {
  connecting.value = true
  error.value = ''
  try {
    const result = await post('/pluggy/connect-token/', {
      institution_id: props.institution.id,
    })
    // Open Pluggy embed with the token
    if (result.access_token) {
      const config = useRuntimeConfig()
      window.open(
        `${config.public.pluggyConnectUrl}/embed?token=${result.access_token}`,
        '_blank',
      )
      emit('connected')
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erro ao iniciar conexão.'
  } finally {
    connecting.value = false
  }
}
</script>

<template>
  <div class="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
    <div class="flex items-center gap-3">
      <img
        v-if="props.institution.logo_url"
        :src="props.institution.logo_url"
        :alt="props.institution.name"
        class="h-8 w-8 rounded-full object-contain"
      >
      <div v-else class="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
        <Icon icon="mdi:bank" class="h-5 w-5" />
      </div>
      <span class="text-sm font-medium text-slate-900">{{ props.institution.name }}</span>
    </div>
    <button
      :disabled="connecting"
      class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      @click="connect"
    >
      {{ connecting ? 'Conectando...' : 'Conectar' }}
    </button>
  </div>
</template>
