const publicRoutes = ['/', '/login', '/register']

export default defineNuxtRouteMiddleware((to) => {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated.value && !publicRoutes.includes(to.path)) {
    return navigateTo('/login')
  }

  if (isAuthenticated.value && (to.path === '/login' || to.path === '/register')) {
    return navigateTo('/dashboard')
  }
})
