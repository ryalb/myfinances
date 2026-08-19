import { computed, reactive, ref } from 'vue'

interface CurrentUser {
  id: number
  email: string
  first_name: string
  last_name: string
  avatar_url: string
}

export function useCurrentUser() {
  const user = ref<CurrentUser | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchUser = async () => {
    if (user.value) return user.value
    loading.value = true
    error.value = null
    try {
      const data = await useApi().get<CurrentUser>('/auth/me/')
      if (data) {
        user.value = data
      }
      return data
    } catch {
      error.value = 'Failed to load user'
      return null
    } finally {
      loading.value = false
    }
  }

  const fullName = computed(() => {
    if (!user.value) return ''
    const { first_name, last_name } = user.value
    return [first_name, last_name].filter(Boolean).join(' ') || user.value.email
  })

  const initials = computed(() => {
    if (!user.value) return '?'
    const { first_name, last_name, email } = user.value
    if (first_name || last_name) {
      return [first_name, last_name].filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2)
    }
    return email.slice(0, 2).toUpperCase()
  })

  const gravatarUrl = computed(() => user.value?.avatar_url ?? '')

  return reactive({
    user,
    loading,
    error,
    fetchUser,
    fullName,
    initials,
    gravatarUrl,
  })
}
