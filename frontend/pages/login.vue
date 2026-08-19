<script setup lang="ts">
import Button from 'primevue/button'

definePageMeta({ layout: false })
const router = useRouter()
const { login, isAuthenticated } = useAuth()

if (isAuthenticated.value) {
  router.push('/dashboard')
}

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showPassword = ref(false)

const handleSubmit = async () => {
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
  <div class="flex min-h-screen w-full bg-sepia-50">
    <!-- Capa: mesma metáfora do logo (livro-razão aberto) em tamanho real. -->
    <div class="hidden lg:flex lg:w-[44%] flex-col justify-between bg-sepia-950 p-12 text-sepia-100">
      <NuxtLink to="/" class="flex items-center gap-3">
        <img src="/logo.png" alt="MyFinances" class="h-9 w-auto">
        <span class="font-display text-xl font-semibold text-sepia-50">MyFinances</span>
      </NuxtLink>

      <div class="max-w-md">
        <p class="mb-3 text-xs font-medium uppercase tracking-widest text-sepia-400">Seu extrato pessoal</p>
        <h2 class="font-display text-3xl font-semibold leading-tight text-sepia-50">
          Todo o seu patrimônio, lançado numa página só.
        </h2>
        <p class="mt-4 text-sm leading-relaxed text-sepia-300">
          Contas, cartões, investimentos e previdência — conectados via Open Finance e atualizados sozinhos.
        </p>

        <ul class="mt-8 space-y-3 border-t border-sepia-800 pt-6 text-sm text-sepia-300">
          <li class="flex items-center gap-2">
            <Icon icon="mdi:check" class="h-4 w-4 text-azul-300" />
            Contas, cartões e investimentos num só lugar
          </li>
          <li class="flex items-center gap-2">
            <Icon icon="mdi:check" class="h-4 w-4 text-azul-300" />
            Projeção de liberdade financeira
          </li>
          <li class="flex items-center gap-2">
            <Icon icon="mdi:check" class="h-4 w-4 text-azul-300" />
            Sincronização automática, sem planilhas
          </li>
        </ul>
      </div>

      <p class="text-xs text-sepia-500">Dados protegidos e sincronizados via Open Finance.</p>
    </div>

    <!-- Página: formulário de acesso -->
    <div class="flex flex-1 items-center justify-center px-6 py-12 sm:px-12">
      <div class="w-full max-w-sm">
        <div class="mb-8 text-center lg:hidden">
          <img src="/logo.png" alt="MyFinances" class="mx-auto mb-3 h-16 w-auto">
          <span class="font-display text-xl font-semibold text-sepia-900">MyFinances</span>
        </div>

        <p class="text-xs font-medium uppercase tracking-widest text-sepia-400">Bem-vindo de volta</p>
        <h1 class="font-display mt-1 text-3xl font-semibold text-sepia-900">
          Entrar
        </h1>
        <p class="mt-2 text-sm text-sepia-500">Digite seu email e senha para acessar sua conta.</p>

        <form class="mt-8 space-y-6" @submit.prevent="handleSubmit">
          <div>
            <label class="mb-1.5 block text-sm font-medium text-sepia-700">
              Email <span class="text-vermelho-500">*</span>
            </label>
            <input
              v-model="email"
              type="email"
              placeholder="voce@email.com"
              class="h-11 w-full rounded-none border-0 border-b-2 border-sepia-200 bg-transparent px-1 text-sm text-sepia-900 placeholder:text-sepia-400 focus:border-sepia-500 focus:outline-none focus:ring-0"
            >
          </div>

          <div>
            <label class="mb-1.5 block text-sm font-medium text-sepia-700">
              Senha <span class="text-vermelho-500">*</span>
            </label>
            <div class="relative">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="Digite sua senha"
                class="h-11 w-full rounded-none border-0 border-b-2 border-sepia-200 bg-transparent px-1 pr-9 text-sm text-sepia-900 placeholder:text-sepia-400 focus:border-sepia-500 focus:outline-none focus:ring-0"
              >
              <button
                type="button"
                class="absolute top-1/2 right-1 -translate-y-1/2 text-sepia-400 hover:text-sepia-600"
                :aria-label="showPassword ? 'Ocultar senha' : 'Mostrar senha'"
                @click="showPassword = !showPassword"
              >
                <Icon :icon="showPassword ? 'mdi:eye-off-outline' : 'mdi:eye-outline'" class="h-5 w-5" />
              </button>
            </div>
          </div>

          <p v-if="error" class="text-sm text-vermelho-600">{{ error }}</p>

          <Button
            type="submit"
            :disabled="loading"
            class="!flex !w-full !items-center !justify-center !rounded-md !bg-sepia-900 !px-4 !py-3 !text-sm !font-medium !text-sepia-50 hover:!bg-sepia-950 disabled:!opacity-50"
          >
            {{ loading ? 'Entrando...' : 'Entrar' }}
          </Button>
        </form>

        <p class="mt-6 text-center text-sm text-sepia-600">
          Ainda não tem conta?
          <NuxtLink to="/register" class="font-medium text-sepia-800 underline decoration-sepia-300 hover:text-sepia-950">
            Cadastre-se
          </NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>
