export function useAuth() {
  const config = useRuntimeConfig()
  const accessToken = useCookie<string | null>('access_token')
  const refreshToken = useCookie<string | null>('refresh_token')

  const isAuthenticated = computed(() => !!accessToken.value)

  const login = async (email: string, password: string) => {
    const data = await $fetch<{ access: string; refresh: string }>(
      `${config.public.apiBaseUrl}/auth/token/`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
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

  const refresh = async () => {
    if (!refreshToken.value) return false

    try {
      const data = await $fetch<{ access: string }>(
        `${config.public.apiBaseUrl}/auth/token/refresh/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh: refreshToken.value }),
        },
      )
      accessToken.value = data.access
      return true
    } catch {
      logout()
      return false
    }
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
