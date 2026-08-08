export function useApi() {
  const config = useRuntimeConfig()
  const token = useCookie<string | null>('access_token')
  const router = useRouter()
  const { logout } = useAuth()

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

  const get = async <T>(path: string): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, { headers: getHeaders() })
    } catch (error) {
      if ((error as { status?: number }).status === 401) handleUnauthorized()
      return null
    }
  }

  const post = async <T>(path: string, body: Record<string, unknown>): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method: 'POST',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body,
      })
    } catch (error) {
      if ((error as { status?: number }).status === 401) handleUnauthorized()
      return null
    }
  }

  const patch = async <T>(path: string, body: Record<string, unknown>): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method: 'PATCH',
        headers: { ...getHeaders(), 'Content-Type': 'application/json' },
        body,
      })
    } catch (error) {
      if ((error as { status?: number }).status === 401) handleUnauthorized()
      return null
    }
  }

  const del = async <T>(path: string): Promise<T | null> => {
    try {
      return await $fetch<T>(`${config.public.apiBaseUrl}${path}`, {
        method: 'DELETE',
        headers: getHeaders(),
      })
    } catch (error) {
      if ((error as { status?: number }).status === 401) handleUnauthorized()
      return null
    }
  }

  return { get, post, patch, del, getHeaders }
}
