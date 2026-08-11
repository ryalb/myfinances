<script setup lang="ts">
import { formatIsoDateTime } from '@/composables/useDateFormat'

type SyncJobRow = {
  id: number
  connection: number
  institution_name: string
  kind: string
  status: string
  started_at: string | null
  finished_at: string | null
  error_message: string
  created_at: string
}

// `/sync-jobs/` passou a vir paginado: a coleção cresce um registro por sync e
// não tem teto natural.
const { items: jobs, count } = usePaginatedList<SyncJobRow>('sync-jobs', '/sync-jobs/', {
  pageSize: 20,
})

const statusColors: Record<string, string> = {
  queued: 'bg-sepia-100 text-sepia-600',
  running: 'bg-sepia-100 text-sepia-700',
  success: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-rose-100 text-rose-700',
}

const formatTime = formatIsoDateTime
</script>

<template>
  <div class="overflow-hidden rounded-xl border border-sepia-200 bg-white shadow-sm">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-sepia-200 bg-sepia-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Instituição</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Status</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Tipo</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Início</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Fim</th>
            <th class="px-4 py-3 text-left font-medium text-sepia-600">Erro</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!jobs.length" class="border-b border-sepia-100">
            <td colspan="6" class="px-4 py-8 text-center text-sepia-400">Nenhuma sincronização registrada.</td>
          </tr>
          <tr v-for="job in jobs" :key="job.id" class="border-b border-sepia-100 last:border-0">
            <td class="px-4 py-3 font-medium text-sepia-900">{{ job.institution_name }}</td>
            <td class="px-4 py-3">
              <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', statusColors[job.status] || 'bg-sepia-100 text-sepia-600']">
                {{ job.status }}
              </span>
            </td>
            <td class="px-4 py-3 text-sepia-600">{{ job.kind }}</td>
            <td class="px-4 py-3 text-sepia-500">{{ formatTime(job.started_at) }}</td>
            <td class="px-4 py-3 text-sepia-500">{{ formatTime(job.finished_at) }}</td>
            <td class="px-4 py-3">
              <span v-if="job.error_message" class="text-xs text-rose-600">{{ job.error_message.slice(0, 60) }}...</span>
              <span v-else class="text-sepia-400">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="count > jobs.length" class="border-t border-sepia-200 px-4 py-2 text-xs text-sepia-400">
      Mostrando {{ jobs.length }} de {{ count }} sincronizações.
    </p>
  </div>
</template>
