<script setup lang="ts">
const router = useRouter()
const { login } = useAuth()

const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

const submit = async () => {
  if (!email.value || !password.value) {
    error.value = 'Preencha todos os campos.'
    return
  }

  if (password.value !== confirmPassword.value) {
    error.value = 'As senhas não coincidem.'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await $fetch(`${useRuntimeConfig().public.apiBaseUrl}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })

    await login(email.value, password.value)
    router.push('/dashboard')
  } catch {
    error.value = 'Não foi possível criar a conta.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50">
    <div class="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 class="mb-1 text-2xl font-semibold text-slate-900">Criar conta</h1>
      <p class="mb-6 text-sm text-slate-500">Comece a organizar suas finanças</p>

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

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700">Confirmar senha</label>
          <input
            v-model="confirmPassword"
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
          {{ loading ? 'Criando conta...' : 'Criar conta' }}
        </button>
      </form>

      <p class="mt-4 text-center text-sm text-slate-500">
        Já tem conta?
        <NuxtLink to="/login" class="text-slate-900 underline">Entrar</NuxtLink>
      </p>
    </div>
  </div>
</template>
