import type { Paginated } from '@/composables/useApi'

const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] }

/**
 * Lista paginada do DRF com navegação de página e filtros.
 *
 * Existe para o formato do envelope (`{count, next, previous, results}`) ficar num
 * lugar só: espalhar `.results` pelas telas faz cada uma tratar o caso vazio de um
 * jeito diferente.
 */
export function usePaginatedList<T>(
  key: string,
  path: string,
  options: { pageSize?: number, params?: () => Record<string, string> } = {},
) {
  const { get } = useApi()
  const page = ref(1)

  const queryString = computed(() => {
    const params = new URLSearchParams({ page: String(page.value) })
    if (options.pageSize) params.set('page_size', String(options.pageSize))
    for (const [name, value] of Object.entries(options.params?.() ?? {})) {
      if (value !== '' && value != null) params.set(name, value)
    }
    return params.toString()
  })

  // Só a parte de filtro, sem `page`: serve para detectar mudança de filtro e
  // voltar para a primeira página. Sem isso, filtrar estando na página 7 pediria a
  // página 7 de um resultado que talvez tenha uma só — e a tela viria vazia.
  const filterSignature = computed(() => JSON.stringify(options.params?.() ?? {}))

  watch(filterSignature, () => {
    page.value = 1
  })

  const { data, refresh, status } = useAsyncData(
    key,
    async () => (await get<Paginated<T>>(`${path}?${queryString.value}`)) ?? EMPTY_PAGE,
    { default: () => EMPTY_PAGE as Paginated<T>, watch: [queryString] },
  )

  const items = computed(() => data.value?.results ?? [])
  const count = computed(() => data.value?.count ?? 0)
  const pageSize = computed(() => options.pageSize ?? 100)
  const totalPages = computed(() => Math.max(1, Math.ceil(count.value / pageSize.value)))
  const hasNext = computed(() => Boolean(data.value?.next))
  const hasPrevious = computed(() => Boolean(data.value?.previous))
  const loading = computed(() => status.value === 'pending')

  const next = () => {
    if (hasNext.value) page.value += 1
  }

  const previous = () => {
    if (hasPrevious.value) page.value -= 1
  }

  return {
    items,
    count,
    page,
    pageSize,
    totalPages,
    hasNext,
    hasPrevious,
    loading,
    next,
    previous,
    refresh,
    queryString,
  }
}
