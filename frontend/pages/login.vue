<script setup lang="ts">
const router = useRouter()
const { login, isAuthenticated } = useAuth()

if (isAuthenticated.value) {
  router.push('/dashboard')
}

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const submit = async () => {
  if (!email.value || !password.value) {
    error.value = 'Preencha email e senha.'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await login(email.value, password.value)
    router.push('/dashboard')
  } catch {
    error.value = 'Credenciais inválidas.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50">
    <div class="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 class="mb-1 text-2xl font-semibold text-slate-900">Entrar</h1>
      <p class="mb-6 text-sm text-slate-500">Acesse sua conta MyFinances</p>

      <form class="space-y-4" @submit.prevent="submit">
        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <input
            v-model="email"
            type="email"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
            placeholder="voce@email.com"
          >
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700">Senha</label>
          <input
            v-model="password"
            type="password"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
            placeholder="••••••••"
          >
        </div>

        <p v-if="error" class="text-sm text-rose-600">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {{ loading ? 'Entrando...' : 'Entrar' }}
        </button>
      </form>

      <p class="mt-4 text-center text-sm text-slate-500">
        Ainda não tem conta?
        <NuxtLink to="/register" class="text-slate-900 underline">Cadastre-se</NuxtLink>
      </p>
    </div>
  </div>
</template>
