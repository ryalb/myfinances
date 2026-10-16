<script setup lang="ts">
import { useSidebarProvider } from '@/composables/useSidebar'
import { useRealtimeSync } from '@/composables/useRealtimeSync'
import { usePageLoading } from '@/composables/usePageLoading'

const { isExpanded, isHovered } = useSidebarProvider()
const { pageLoading } = usePageLoading()

const { isAuthenticated: _isAuthenticated, logout } = useAuth()
const { connect: _connectRealtime } = useRealtimeSync()
const router = useRouter()

const _handleLogout = () => {
  logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen xl:flex bg-sepia-950 print:min-h-0 print:block print:bg-white">
    <LayoutAppSidebar />
    <LayoutBackdrop />
    <div
      class="flex-1 min-h-screen bg-sepia-50 text-sepia-900 transition-all duration-300 ease-in-out print:!ml-0 print:min-h-0 print:bg-white"
      :class="[isExpanded || isHovered ? 'lg:ml-[290px]' : 'lg:ml-[90px]']"
    >
      <LayoutAppHeader />
      <main class="p-4 mx-auto max-w-(--breakpoint-2xl) md:p-6 print:p-0 print:max-w-none">
        <div
          v-if="pageLoading"
          role="status"
          aria-live="polite"
          class="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-sepia-500"
        >
          <AppSpinner class="text-sepia-700" />
          <span class="text-sm">Carregando…</span>
        </div>
        <!-- `v-show`, nao `v-if`: a pagina precisa estar montada por baixo do
             spinner para disparar as proprias requisicoes. -->
        <div v-show="!pageLoading">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
