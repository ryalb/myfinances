// Envelope do PageNumberPagination do DRF. Só as coleções que crescem sem limite
// (transações, sync jobs) vêm assim; as listas pequenas seguem como array puro.
export type Paginated<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// Extrai mensagem legível de um erro do DRF. O corpo de um 400 vem como
// `{campo: ["msg"], ...}`; os endpoints operacionais usam `{detail: ...}` ou
// `{error: ...}`. Sem isso o usuário veria "[object Object]" ou nada.
export function extractApiError(error: unknown, fallback: string): string {
  const data = (error as { data?: unknown })?.data
  if (typeof data === 'string' && data) return data
  if (data && typeof data === 'object') {
    const body = data as Record<string, unknown>
    for (const key of ['detail', 'error'] as const) {
      if (typeof body[key] === 'string' && body[key]) return body[key] as string
    }
    const parts = Object.entries(body).map(([field, messages]) => {
      const text = Array.isArray(messages) ? messages.join(' ') : String(messages)
      return field === 'non_field_errors' ? text : `${field}: ${text}`
    })
    if (parts.length) return parts.join(' · ')
  }
  return error instanceof Error && error.message ? error.message : fallback
}

export function useApi() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const router = useRouter()
  const { logout, refresh } = useAuth()

  const getHeaders = (): Record<string, string> => {
    const base: Record<string, string> = {}
    if (token.value) {
      base.Authorization = `Bearer ${token.value}`
    }
    return base
  }

  const handleUnauthorized = () => {
    const path = router.currentRoute.value.path
    const isAuthPage = path === '/login' || path === '/register'
    if (!isAuthPage) {
      logout()
      router.push('/login')
    }
  }

  // Um 401 quase sempre é o access token expirando no meio da sessão (vida
  // curta de 5min) — não a sessão em si. Tenta renovar e refazer a chamada
  // uma vez antes de deslogar; só desloga se o refresh token também falhar.
  const isUnauthorized = (error: unknown) => (error as { status?: number })?.status === 401

  const get = async <T>(path: string): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, { headers: getHeaders() })
    } catch (error) {
      if (!isUnauthorized(error)) return null
      if (await refresh()) {
        try {
          return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, { headers: getHeaders() })
        } catch {
          handleUnauthorized()
          return null
        }
      }
      handleUnauthorized()
      return null
    }
  }

  // Escritas propagam o erro depois de tratar o 401. Devolver `null` numa falha
  // de validação faz o formulário parecer ter salvo: o chamador não tem como
  // distinguir sucesso de 400 e o usuário não recebe mensagem nenhuma.
  const write = async <T>(method: 'POST' | 'PATCH' | 'DELETE', path: string, body?: Record<string, unknown>): Promise<T | null> => {
    const attempt = () =>
      $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method,
        headers: body ? { ...getHeaders(), 'Content-Type': 'application/json' } : getHeaders(),
        body,
      })

    try {
      return await attempt()
    } catch (error) {
      if (!isUnauthorized(error)) throw error
      if (await refresh()) {
        try {
          return await attempt()
        } catch (retryError) {
          if (isUnauthorized(retryError)) {
            handleUnauthorized()
            return null
          }
          throw retryError
        }
      }
      handleUnauthorized()
      return null
    }
  }

  const post = <T>(path: string, body: Record<string, unknown>) => write<T>('POST', path, body)
  const patch = <T>(path: string, body: Record<string, unknown>) => write<T>('PATCH', path, body)
  const del = <T>(path: string) => write<T>('DELETE', path)

  // Mesma renovação de token dos endpoints REST, para as queries GraphQL que
  // hoje montam o fetch na mão em cada composable.
  const graphql = async <T>(query: string, variables?: Record<string, unknown>): Promise<T | null> => {
    const attempt = () =>
      $fetch<T>(config.public.graphqlEndpoint as string, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: variables ? { query, variables } : { query },
      })

    try {
      return await attempt()
    } catch (error) {
      if (!isUnauthorized(error)) return null
      if (await refresh()) {
        try {
          return await attempt()
        } catch {
          handleUnauthorized()
          return null
        }
      }
      handleUnauthorized()
      return null
    }
  }

  /**
   * Baixa um arquivo do backend.
   *
   * Não dá para usar `<a href>`: o endpoint exige o header Authorization, e o
   * navegador não o envia numa navegação normal. Daí o fetch + blob.
   */
  const download = async (path: string, filename: string) => {
    const blob = await $fetch<Blob>(`${config.public.apiBaseUrl}${path}`, {
      headers: getHeaders(),
      responseType: 'blob',
    })
    const url = URL.createObjectURL(blob)
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
    } finally {
      // Sem o revoke o blob fica retido até a aba fechar.
      URL.revokeObjectURL(url)
    }
  }

  return { get, post, patch, del, download, graphql, getHeaders }
}
