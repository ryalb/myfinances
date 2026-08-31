import DOMPurify from 'dompurify'
import { marked } from 'marked'

// `breaks: true`: o modelo separa parágrafos com uma linha só às vezes, não
// sempre duas -- sem isso a resposta vira um bloco só de texto colado.
marked.setOptions({ breaks: true })

// Sanitiza depois de converter: o texto vem de um modelo de linguagem, não de
// uma fonte confiável, então `v-html` sem isso seria um vetor de XSS.
export function renderMarkdownToHtml(text: string): string {
  const html = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(html)
}
