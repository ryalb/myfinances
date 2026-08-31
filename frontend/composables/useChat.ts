import type { ReportSource } from '@/composables/useAiReport'

export type ChatMessage = {
  id: number | string
  role: 'user' | 'assistant'
  content: string
  sources: ReportSource[]
  created_at: string
  // Só existe no lado do cliente enquanto a resposta ainda está chegando --
  // nunca vem do backend, que só grava a mensagem completa ao final do stream.
  streaming?: boolean
}

// O Ollama manda pedaços de tamanho irregular (às vezes uma palavra inteira de
// uma vez) -- passar isso direto pro conteúdo faz o texto "pular" em vez de
// parecer digitado. Este buffer revela poucos caracteres por vez, num ritmo
// constante, independente de como o backend agrupou os pedaços.
const REVEAL_CHARS_PER_TICK = 2
const REVEAL_INTERVAL_MS = 20

async function streamWithTypingEffect(body: ReadableStream<Uint8Array>, message: ChatMessage) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  let readerDone = false

  const readLoop = (async () => {
    let chunk = await reader.read()
    while (!chunk.done) {
      pending += decoder.decode(chunk.value, { stream: true })
      chunk = await reader.read()
    }
    readerDone = true
  })()

  await new Promise<void>((resolve) => {
    const tick = () => {
      if (pending.length) {
        message.content += pending.slice(0, REVEAL_CHARS_PER_TICK)
        pending = pending.slice(REVEAL_CHARS_PER_TICK)
        setTimeout(tick, REVEAL_INTERVAL_MS)
      } else if (readerDone) {
        resolve()
      } else {
        setTimeout(tick, REVEAL_INTERVAL_MS)
      }
    }
    tick()
  })

  await readLoop
}

export function useChat() {
  const config = useRuntimeConfig()
  const { get, del, getHeaders } = useApi()
  const { refresh } = useAuth()

  const { data: messages, refresh: reloadHistory } = useAsyncData<ChatMessage[]>(
    'chat-history',
    async () => (await get<ChatMessage[]>('/ai/chat/')) ?? [],
    { default: () => [] },
  )

  const sending = ref(false)
  const error = ref('')

  const postMessage = (text: string) =>
    fetch(`${config.public.apiBaseUrl}/ai/chat/`, {
      method: 'POST',
      headers: { ...getHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || sending.value) return
    sending.value = true
    error.value = ''

    const localId = `local-${Date.now()}`
    const userMessage: ChatMessage = {
      id: localId,
      role: 'user',
      content: trimmed,
      sources: [],
      created_at: new Date().toISOString(),
    }
    // Mesma referência é anexada ao array e mutada abaixo -- a reatividade
    // profunda do Vue nisso é o que faz o texto crescer na tela conforme os
    // pedaços chegam, sem precisar recriar o array a cada chunk.
    const assistantMessage: ChatMessage = {
      id: `${localId}-reply`,
      role: 'assistant',
      content: '',
      sources: [],
      created_at: new Date().toISOString(),
      streaming: true,
    }
    messages.value = [...(messages.value ?? []), userMessage, assistantMessage]

    try {
      let response = await postMessage(trimmed)
      if (response.status === 401) {
        if (!(await refresh())) throw new Error('Sessão expirada. Faça login novamente.')
        response = await postMessage(trimmed)
      }
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.error || body?.detail || 'Erro ao enviar a mensagem.')
      }

      await streamWithTypingEffect(response.body, assistantMessage)

      // Recarrega do backend para trocar as mensagens locais pelas
      // persistidas (com id real e `sources`) -- o corpo em streaming nunca
      // traz as fontes usadas, só o texto.
      await reloadHistory()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Erro ao enviar a mensagem.'
      messages.value = (messages.value ?? []).filter(
        (m) => m.id !== userMessage.id && m.id !== assistantMessage.id,
      )
    } finally {
      sending.value = false
    }
  }

  const clearHistory = async () => {
    await del('/ai/chat/')
    messages.value = []
  }

  return { messages, sending, error, sendMessage, clearHistory, reloadHistory }
}
