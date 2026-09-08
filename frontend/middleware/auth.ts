const publicRoutes = ['/login', '/register']

export default defineNuxtRouteMiddleware(async (to) => {
  const { accessToken, refreshToken, refresh } = useAuth()

  // Sem access token: so vale a pena tentar recuperar a sessao se ha refresh
  // token (valido por 1 dia, default do SimpleJWT) para trocar por um novo.
  // Chamava `/auth/debug-token/` antes, que foi removido por decisao de
  // seguranca (ver docs/plan.md) -- toda tentativa de recuperacao falhava e
  // caia direto pro login, mesmo com refresh token ainda valido.
  if (!accessToken.value && !publicRoutes.includes(to.path)) {
    const restored = refreshToken.value ? await refresh() : false
    if (!restored) {
      return navigateTo('/login')
    }
  }

  if (accessToken.value && (to.path === '/login' || to.path === '/register')) {
    return navigateTo('/dashboard')
  }
})
