// Módulo (não closure): várias composables chamam refresh() no mesmo instante
// quando o access token expira (várias requests em paralelo levam 401 juntas).
// Sem isso cada uma dispara sua própria /auth/token/refresh/.
let refreshPromise: Promise<boolean> | null = null

export function useAuth() {
  const config = useRuntimeConfig()
  const accessToken = useCookie<string | null>('access_token')
  const refreshToken = useCookie<string | null>('refresh_token')

  const isAuthenticated = computed(() => !!accessToken.value)

  const login = async (username: string, password: string) => {
    const data = await $fetch<{ access: string; refresh: string }>(
      `${config.public.apiBaseUrl}/auth/token/`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: { username, password },
      },
    )

    accessToken.value = data.access
    refreshToken.value = data.refresh
    return data
  }

  const logout = () => {
    accessToken.value = null
    refreshToken.value = null
  }

  const refresh = (): Promise<boolean> => {
    if (!refreshToken.value) {
      logout()
      return Promise.resolve(false)
    }
    if (refreshPromise) return refreshPromise

    refreshPromise = (async () => {
      try {
        const data = await $fetch<{ access: string }>(
          `${config.public.apiBaseUrl}/auth/token/refresh/`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: { refresh: refreshToken.value },
          },
        )
        accessToken.value = data.access
        return true
      } catch {
        logout()
        return false
      } finally {
        refreshPromise = null
      }
    })()

    return refreshPromise
  }

  return {
    accessToken,
    refreshToken,
    isAuthenticated,
    login,
    logout,
    refresh,
  }
}
