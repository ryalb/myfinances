<script setup lang="ts">
import { useSidebarProvider } from '@/composables/useSidebar'
import { useRealtimeSync } from '@/composables/useRealtimeSync'

const { isExpanded, isHovered } = useSidebarProvider()

const { isAuthenticated: _isAuthenticated, logout } = useAuth()
const { connect: _connectRealtime } = useRealtimeSync()
const router = useRouter()

const _handleLogout = () => {
  logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen xl:flex bg-sepia-950">
    <LayoutAppSidebar />
    <LayoutBackdrop />
    <div
      class="flex-1 min-h-screen bg-sepia-50 text-sepia-900 transition-all duration-300 ease-in-out"
      :class="[isExpanded || isHovered ? 'lg:ml-[290px]' : 'lg:ml-[90px]']"
    >
      <LayoutAppHeader />
      <main class="p-4 mx-auto max-w-(--breakpoint-2xl) md:p-6">
        <slot />
      </main>
    </div>
  </div>
</template>
