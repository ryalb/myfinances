<script setup lang="ts">
import Button from 'primevue/button'
import { sourceLabel } from '@/composables/useAiReport'
import { renderMarkdownToHtml } from '@/composables/useMarkdown'

definePageMeta({
  middleware: 'auth',
})

const { messages, sending, error, sendMessage, clearHistory } = useChat()
const draft = ref('')
const bottomEl = ref<HTMLElement | null>(null)

const onSend = async () => {
  const text = draft.value
  if (!text.trim() || sending.value) return
  draft.value = ''
  await sendMessage(text)
}

const clearing = ref(false)
const onClear = async () => {
  if (!messages.value?.length) return
  if (!window.confirm('Limpar toda a conversa? Essa ação não pode ser desfeita.')) return
  clearing.value = true
  try {
    await clearHistory()
  } finally {
    clearing.value = false
  }
}

// Rola para a última mensagem a cada novo turno ou pedaço do streaming --
// sem isso a resposta cresce fora da área visível conforme o texto chega.
watch(
  messages,
  async () => {
    await nextTick()
    bottomEl.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  },
  { deep: true },
)
</script>

<template>
  <section class="flex flex-col gap-4">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h1 class="text-2xl font-semibold">Chat IA</h1>
        <p class="mt-1 text-sepia-600">
          Converse sobre seus dados financeiros -- contas, investimentos, cartões, assinaturas e
          transações -- com um modelo rodando localmente.
        </p>
      </div>
      <button
        type="button"
        :disabled="clearing || !messages?.length"
        class="shrink-0 text-xs text-vermelho-600 hover:underline disabled:opacity-50"
        @click="onClear"
      >
        {{ clearing ? 'Limpando...' : 'Limpar conversa' }}
      </button>
    </div>

    <p class="rounded-lg border border-sepia-200 bg-sepia-50 px-4 py-3 text-xs text-sepia-600">
      <Icon icon="mdi:information-outline" class="mr-1 inline h-4 w-4 align-text-bottom" />
      Respostas geradas automaticamente a partir dos seus próprios dados, por um modelo de
      linguagem rodando localmente. Não é recomendação de investimento nem consultoria
      financeira: confira os números na fonte antes de decidir.
    </p>

    <p v-if="error" class="rounded-lg border border-vermelho-200 bg-vermelho-50 px-4 py-3 text-sm text-vermelho-700">
      {{ error }}
    </p>

    <div class="min-h-[50vh] space-y-4 rounded-lg border border-sepia-200 bg-white p-4 shadow-sm">
      <div
        v-if="!messages?.length"
        class="flex h-full min-h-[50vh] flex-col items-center justify-center text-center"
      >
        <Icon icon="mdi:chat-question-outline" class="mb-3 h-10 w-10 text-sepia-300" />
        <p class="text-sepia-500">Nenhuma conversa ainda.</p>
        <p class="mt-1 text-sm text-sepia-400">
          Pergunte algo como "como estão meus investimentos" ou "quanto gastei em assinaturas
          este mês".
        </p>
      </div>

      <div
        v-for="message in messages"
        :key="message.id"
        :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']"
      >
        <div
          :class="[
            'max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed shadow-sm',
            message.role === 'user'
              ? 'bg-sepia-900 text-sepia-50'
              : 'border border-sepia-200 bg-sepia-50 text-sepia-800',
          ]"
        >
          <div v-if="message.streaming && !message.content" class="flex items-center gap-1 py-1">
            <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-sepia-400" />
            <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-sepia-400 [animation-delay:150ms]" />
            <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-sepia-400 [animation-delay:300ms]" />
          </div>
          <template v-else-if="message.role === 'assistant'">
            <div class="markdown-body" v-html="renderMarkdownToHtml(message.content)" />
            <div v-if="message.streaming" class="mt-1.5 flex items-center gap-1">
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-sepia-400" />
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-sepia-400 [animation-delay:150ms]" />
              <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-sepia-400 [animation-delay:300ms]" />
            </div>
          </template>
          <p v-else class="whitespace-pre-line">{{ message.content }}</p>
          <ul
            v-if="message.sources?.length"
            class="mt-2 flex flex-wrap gap-1.5 border-t border-sepia-200 pt-2"
          >
            <li
              v-for="source in message.sources"
              :key="`${source.source_type}-${source.source_id}`"
              class="rounded-full border border-sepia-200 bg-white px-2 py-0.5 text-[11px] text-sepia-500"
            >
              {{ sourceLabel(source) }}
            </li>
          </ul>
        </div>
      </div>
      <div ref="bottomEl" />
    </div>

    <!-- `sticky bottom-0`: fica visível sem depender de calcular a altura exata do
    cabeçalho/padding do layout -- calcular isso em `vh` deixava a caixa de texto
    fora da tela em algumas resoluções, exigindo rolar a página para digitar. -->
    <form
      class="sticky bottom-0 z-10 flex gap-2 border-t border-sepia-200 bg-sepia-50 py-3"
      @submit.prevent="onSend"
    >
      <input
        v-model="draft"
        type="text"
        placeholder="Pergunte sobre seus investimentos, gastos, metas..."
        :disabled="sending"
        class="flex-1 rounded-lg border border-sepia-300 px-3 py-2 text-sm focus:border-sepia-500 focus:outline-none focus:ring-1 focus:ring-sepia-500 disabled:opacity-50"
      >
      <Button
        type="submit"
        :disabled="sending || !draft.trim()"
        class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-medium !text-white hover:!bg-sepia-950 disabled:!opacity-50 whitespace-nowrap shrink-0"
      >
        {{ sending ? 'Enviando...' : 'Enviar' }}
      </Button>
    </form>
  </section>
</template>

<style scoped>
/* Estilo mínimo pro HTML vindo de `renderMarkdownToHtml` -- o Tailwind não
alcança elementos injetados via v-html sem essas regras `:deep()`. */
.markdown-body :deep(p) {
  margin-bottom: 0.5rem;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(strong) {
  font-weight: 600;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.25rem 0 0.5rem 1.25rem;
}
.markdown-body :deep(ul) {
  list-style-type: disc;
}
.markdown-body :deep(ol) {
  list-style-type: decimal;
}
.markdown-body :deep(li) {
  margin-bottom: 0.25rem;
}
.markdown-body :deep(code) {
  background: rgb(231 217 184 / 0.5);
  border-radius: 0.25rem;
  padding: 0.1rem 0.3rem;
  font-size: 0.85em;
}
.markdown-body :deep(pre) {
  background: rgb(231 217 184 / 0.5);
  border-radius: 0.375rem;
  padding: 0.5rem;
  overflow-x: auto;
  margin: 0.5rem 0;
}
.markdown-body :deep(pre) code {
  background: transparent;
  padding: 0;
}
.markdown-body :deep(a) {
  text-decoration: underline;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-weight: 600;
  margin: 0.5rem 0 0.25rem;
}
</style>
