<script setup lang="ts">
const config = useRuntimeConfig()
const token = useCookie<string | null>('access_token')
const headers = token.value ? { Authorization: `Bearer ${token.value}` } : {}

const { data: jobs } = await useFetch<
  {
    id: number
    connection: number
    institution_name: string
    kind: string
    status: string
    started_at: string | null
    finished_at: string | null
    error_message: string
    created_at: string
  }[]
>(`${config.public.apiBaseUrl}/sync-jobs/`, {
  key: 'sync-jobs',
  headers,
})

const statusColors: Record<string, string> = {
  queued: 'bg-slate-100 text-slate-600',
  running: 'bg-blue-100 text-blue-700',
  success: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-rose-100 text-rose-700',
}

const formatTime = (d: string | null) => (d ? new Date(d).toLocaleString('pt-BR') : '—')
</script>

<template>
  <div class="rounded-xl border border-slate-200 bg-white shadow-sm">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-slate-200 bg-slate-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Instituição</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Status</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Tipo</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Início</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Fim</th>
            <th class="px-4 py-3 text-left font-medium text-slate-600">Erro</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!jobs?.length" class="border-b border-slate-100">
            <td colspan="6" class="px-4 py-8 text-center text-slate-400">Nenhuma sincronização registrada.</td>
          </tr>
          <tr v-for="job in jobs?.slice(0, 20)" :key="job.id" class="border-b border-slate-100 last:border-0">
            <td class="px-4 py-3 font-medium text-slate-900">{{ job.institution_name }}</td>
            <td class="px-4 py-3">
              <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusColors[job.status] || 'bg-slate-100 text-slate-600']">
                {{ job.status }}
              </span>
            </td>
            <td class="px-4 py-3 text-slate-600">{{ job.kind }}</td>
            <td class="px-4 py-3 text-slate-500">{{ formatTime(job.started_at) }}</td>
            <td class="px-4 py-3 text-slate-500">{{ formatTime(job.finished_at) }}</td>
            <td class="px-4 py-3">
              <span v-if="job.error_message" class="text-xs text-rose-600">{{ job.error_message.slice(0, 60) }}...</span>
              <span v-else class="text-slate-400">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
