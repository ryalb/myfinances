export function useRealtimeSync() {
  const config = useRuntimeConfig()
  const { accessToken } = useAuth()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

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
      console.log('[WebSocket] Connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'sync_event' && (data.status === 'SUCCESS' || data.status === 'FAILED')) {
          refreshNuxtData()
        }
      } catch {
        console.error('[WebSocket] Failed to parse message', event.data)
      }
    }

    ws.onclose = () => {
      ws = null
      if (accessToken.value && reconnectTimer === null) {
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
