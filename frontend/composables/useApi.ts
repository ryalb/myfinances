export function useApi() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')

  const getHeaders = (): Record<string, string> => {
    const base: Record<string, string> = {}
    if (token.value) {
      base.Authorization = `Bearer ${token.value}`
    }
    return base
  }

  const get = async <T>(path: string): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, { headers: getHeaders() })
    } catch {
      return null
    }
  }

  const post = async <T>(path: string, body: Record<string, unknown>): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    } catch {
      return null
    }
  }

  const patch = async <T>(path: string, body: Record<string, unknown>): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method: 'PATCH',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    } catch {
      return null
    }
  }

  const del = async <T>(path: string): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method: 'DELETE',
        headers: getHeaders(),
      })
    } catch {
      return null
    }
  }

  return { get, post, patch, del, getHeaders }
}
