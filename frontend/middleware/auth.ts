const publicRoutes = ['/login', '/register']

export default defineNuxtRouteMiddleware(async (to) => {
  const accessToken = useCookie<string | null>('access_token')
  const refreshToken = useCookie<string | null>('refresh_token')

  if (!accessToken.value && !publicRoutes.includes(to.path)) {
    try {
      const data = await $fetch<{ access: string; refresh: string }>(
        `${useRuntimeConfig().public.apiBaseUrl}/auth/debug-token/`,
        { method: 'POST' }
      )
      accessToken.value = data.access
      refreshToken.value = data.refresh
    } catch {
      return navigateTo('/login')
    }
  }

  if (accessToken.value && (to.path === '/login' || to.path === '/register')) {
    return navigateTo('/dashboard')
  }
})
