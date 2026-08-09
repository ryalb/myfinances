export type Alert = {
  kind: string
  severity: 'danger' | 'warning' | 'info'
  title: string
  detail: string
  actionPath: string
}

const ALERTS_QUERY = `{
  alerts { kind severity title detail actionPath }
}`

export const ALERT_STYLES: Record<Alert['severity'], { chip: string; icon: string; dot: string }> = {
  danger: { chip: 'bg-rose-50 text-rose-700', icon: 'mdi:alert-circle-outline', dot: 'bg-rose-500' },
  warning: { chip: 'bg-amber-50 text-amber-700', icon: 'mdi:alert-outline', dot: 'bg-amber-500' },
  info: { chip: 'bg-sepia-50 text-sepia-700', icon: 'mdi:information-outline', dot: 'bg-sepia-400' },
}

export function useAlerts() {
  const config = useRuntimeConfig()

  // `useAsyncData` e não fetch manual: `useRealtimeSync` chama `refreshNuxtData()`
  // a cada evento de sync, então os alertas se atualizam pelo WebSocket sem polling.
  const { data: alerts, refresh } = useAsyncData<Alert[]>(
    'alerts',
    async () => {
      try {
        const res = await $fetch<{ data?: { alerts?: Alert[] } }>(
          `${config.public.graphqlEndpoint}`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${useCookie<string | null>('access_token').value}`,
              'Content-Type': 'application/json',
            },
            body: { query: ALERTS_QUERY },
          },
        )
        return res?.data?.alerts ?? []
      } catch {
        // Falha aqui não pode derrubar o cabeçalho: o sino simplesmente não aparece.
        return []
      }
    },
    { default: () => [] },
  )

  const count = computed(() => alerts.value?.length ?? 0)
  const actionableCount = computed(
    () => alerts.value?.filter((a) => a.severity !== 'info').length ?? 0,
  )
  const worstSeverity = computed<Alert['severity'] | null>(() => alerts.value?.[0]?.severity ?? null)

  return { alerts, count, actionableCount, worstSeverity, refresh }
}
