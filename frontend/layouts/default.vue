<script setup lang="ts">
const { isAuthenticated, logout } = useAuth()
const router = useRouter()

const handleLogout = () => {
  logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="border-b border-slate-200 bg-white">
      <nav class="mx-auto flex max-w-6xl items-center gap-1 px-6 py-4">
        <NuxtLink to="/" class="font-semibold text-lg">MyFinances</NuxtLink>
        <div v-if="isAuthenticated" class="ml-6 flex gap-1">
          <NuxtLink
            to="/dashboard"
            class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            Dashboard
          </NuxtLink>
          <NuxtLink
            to="/accounts"
            class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            Contas
          </NuxtLink>
          <NuxtLink
            to="/transactions"
            class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            Transações
          </NuxtLink>
          <NuxtLink
            to="/integrations"
            class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            Integrações
          </NuxtLink>
          <NuxtLink
            to="/goals"
            class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            Metas
          </NuxtLink>
        </div>
        <div v-if="isAuthenticated" class="ml-auto">
          <button
            class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            @click="handleLogout"
          >
            Sair
          </button>
        </div>
      </nav>
    </header>
    <main class="mx-auto min-h-screen max-w-6xl px-6 py-8">
      <slot />
    </main>
  </div>
</template>
