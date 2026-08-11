interface SyncEvent {
  status: string
  connectionId: number
  syncJobId: number
}

// Estado compartilhado: `useState` devolve a mesma ref para qualquer chamador,
// entao ConnectionItem.vue reage aos eventos sem abrir uma segunda conexao WS.
export function useSyncEvent() {
  return useState<SyncEvent | null>('lastSyncEvent', () => null)
}

export function useRealtimeSync() {
  const config = useRuntimeConfig()
  const { accessToken, refresh } = useAuth()
  const lastSyncEvent = useSyncEvent()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let consecutiveAuthFailures = 0

  const connect = () => {
    if (!accessToken.value) return

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const apiBaseUrl = config.public.apiBaseUrl
    const wsBaseUrl = apiBaseUrl.replace(/^http/, 'ws').replace(/\/api\/v1\/?$/, '')
    const wsUrl = `${wsBaseUrl}/ws/sync/?token=${encodeURIComponent(accessToken.value)}`

    if (ws) {
      ws.close()
      ws = null
    }

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      consecutiveAuthFailures = 0
      console.log('[WebSocket] Connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'sync_event') {
          lastSyncEvent.value = {
            status: data.status,
            connectionId: data.connection_id,
            syncJobId: data.sync_job_id,
          }
          if (data.status === 'SUCCESS' || data.status === 'FAILED') {
            refreshNuxtData()
          }
        }
      } catch {
        console.error('[WebSocket] Failed to parse message', event.data)
      }
    }

    // Código 4001 = backend rejeitou o token (consumers.py). Reconectar direto
    // repetiria a mesma falha para sempre, já que accessToken.value não muda
    // sozinho — precisa renovar o access token primeiro. Se o refresh também
    // falhar, `refresh()` desloga e o watch abaixo encerra o ciclo. O contador
    // evita um loop apertado (refresh + reconnect sem espera) se o token novo
    // continuar sendo rejeitado por outro motivo.
    ws.onclose = (event) => {
      ws = null
      if (!accessToken.value) return

      if (event.code === 4001 && consecutiveAuthFailures < 3) {
        consecutiveAuthFailures += 1
        refresh().then((ok) => {
          if (ok) connect()
        })
        return
      }

      if (reconnectTimer === null) {
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Error', error)
    }
  }

  onMounted(() => {
    if (import.meta.client) {
      connect()
    }
  })

  onUnmounted(() => {
    if (ws) {
      ws.close()
      ws = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  })

  watch(accessToken, (newToken) => {
    if (newToken) {
      connect()
    } else {
      if (ws) {
        ws.close()
        ws = null
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }
  })

  return { connect }
}
