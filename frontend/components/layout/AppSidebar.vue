<template>
  <aside
    :class="[
      'fixed mt-16 flex flex-col lg:mt-0 top-0 px-4 left-0 bg-sepia-950 text-sepia-100 h-screen transition-all duration-300 ease-in-out z-99999 border-r border-sepia-800',
      {
        'lg:w-[290px]': isExpanded || isMobileOpen || isHovered,
        'lg:w-[90px]': !isExpanded && !isHovered,
        'translate-x-0 w-[290px]': isMobileOpen,
        '-translate-x-full': !isMobileOpen,
        'lg:translate-x-0': true,
      },
    ]"
    @mouseenter="!isExpanded && (isHovered = true)"
    @mouseleave="isHovered = false"
  >
    <div
      :class="[
        'py-6 flex border-b border-sepia-800',
        !isExpanded && !isHovered ? 'lg:justify-center' : 'justify-start',
      ]"
    >
      <NuxtLink to="/" class="flex items-center gap-3">
        <img v-if="isExpanded || isHovered || isMobileOpen" src="/logo.png" alt="MyFinances" class="h-8 w-auto">
        <img v-else src="/logo.png" alt="MF" class="h-8 w-auto">
        <span v-if="isExpanded || isHovered || isMobileOpen" class="font-display text-lg font-semibold text-sepia-50 whitespace-nowrap">MyFinances</span>
      </NuxtLink>
    </div>
    <div
      class="flex-1 flex flex-col overflow-y-auto p-1 pt-4 duration-300 ease-linear no-scrollbar"
    >
      <nav class="mb-6">
        <div class="flex flex-col gap-5">
          <div v-for="(menuGroup, groupIndex) in menuGroups" :key="groupIndex">
            <h2
              v-if="isExpanded || isHovered || isMobileOpen"
              class="mb-3 text-[11px] font-medium uppercase tracking-wider flex leading-[20px] text-sepia-400"
            >
              {{ menuGroup.title }}
            </h2>
            <ul class="flex flex-col gap-1">
              <li v-for="item in menuGroup.items" :key="item.name">
                <NuxtLink
                  v-if="item.path"
                  :to="item.path"
                  :class="[
                    'menu-item group flex items-center gap-3 rounded-md border-l-2 px-2.5 py-2 text-sm transition-colors',
                    isActive(item.path)
                      ? 'border-sepia-300 bg-sepia-900 text-sepia-50'
                      : 'border-transparent text-sepia-300 hover:border-sepia-700 hover:bg-sepia-900/60 hover:text-sepia-50',
                  ]"
                >
                  <span
                    :class="[
                      'flex h-5 w-5 items-center justify-center',
                      isActive(item.path)
                        ? 'text-sepia-300'
                        : 'text-sepia-500 group-hover:text-sepia-300',
                    ]"
                  >
                    <svg v-if="item.path === '/dashboard'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13a8 8 0 0114 0M7 9a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2V9a2 2 0 012-2h2zm8 0a2 2 0 012 2v6a2 2 0 01-2 2h-2a2 2 0 01-2-2V9a2 2 0 012-2h2z"/></svg>
                    <svg v-else-if="item.path === '/accounts'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                    <svg v-else-if="item.path === '/transactions'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>
                     <svg v-else-if="item.path === '/integrations'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                     <svg v-else-if="item.path === '/goals'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                     <svg v-else-if="item.path === '/cards'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                     <svg v-else-if="item.path === '/investments'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                     <svg v-else-if="item.path === '/pension'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                     <svg v-else-if="item.path === '/subscriptions'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                     <svg v-else-if="item.path === '/ai-report'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                     <svg v-else-if="item.path === '/chat'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                     <svg v-else-if="item.path === '/executive-report'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 17V9m3 8V5m3 12v-4M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>
                     <svg v-else-if="item.path === '/rules'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/></svg>
                     <svg v-else-if="item.path === '/simulator'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.5l4.5-4.5 4 4L21 4.5M21 4.5h-5.25M21 4.5v5.25M4.5 19.5h15"/></svg>
                     <svg v-else-if="item.path === '/monthly-review'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2zm5-5l2 2 4-4"/></svg>
                     <svg v-else-if="item.path === '/health-score'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 10-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>
                     <svg v-else-if="item.path === '/portfolio-builder'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/><path stroke-linecap="round" stroke-linejoin="round" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/></svg>
                     <svg v-else-if="item.path === '/optimizer'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.99l1.004.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a7.688 7.688 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                     <!-- Fallback: sem ele, um item de menu novo sem ícone correspondente
                          não renderiza nada e a falha passa despercebida. -->
                     <svg v-else class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>
                  </span>
                  <span
                    v-if="isExpanded || isHovered || isMobileOpen"
                    class="menu-item-text"
                  >
                    {{ item.name }}
                  </span>
                </NuxtLink>
              </li>
            </ul>
          </div>
        </div>
      </nav>
    </div>
    <div class="mt-auto border-t border-sepia-800 py-4">
      <div
        :class="[
          'flex items-center gap-3',
          !isExpanded && !isHovered && !isMobileOpen ? 'lg:justify-center' : 'justify-start',
        ]"
      >
        <Avatar
          v-if="currentUser.user"
          :image="avatarLoadFailed ? undefined : currentUser.gravatarUrl"
          :label="avatarLoadFailed ? currentUser.initials : undefined"
          size="large"
          shape="circle"
          class="!bg-sepia-300 !text-sepia-950 !font-semibold"
          @error="avatarLoadFailed = true"
        />
        <div
          v-if="currentUser.user && (isExpanded || isHovered || isMobileOpen)"
          class="flex flex-col"
        >
          <span class="text-sm font-medium text-sepia-50">{{ currentUser.fullName }}</span>
          <span class="text-xs text-sepia-400">{{ currentUser.user.email }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useSidebar } from '@/composables/useSidebar'
import { useCurrentUser } from '@/composables/useCurrentUser'
import Avatar from 'primevue/avatar'
import { onMounted, ref } from 'vue'

const route = useRoute()
const { isExpanded, isMobileOpen, isHovered } = useSidebar()
const currentUser = useCurrentUser()
const avatarLoadFailed = ref(false)

const isActive = (path: string) => route.path === path

onMounted(() => {
  currentUser.fetchUser()
})

const menuGroups = [
  {
    title: 'Principal',
    items: [
      { name: 'Dashboard', path: '/dashboard' },
      { name: 'Contas', path: '/accounts' },
      { name: 'Transações', path: '/transactions' },
    ],
  },
  {
    title: 'Ferramentas',
    items: [
      { name: 'Integrações', path: '/integrations' },
      { name: 'Metas', path: '/goals' },
      { name: 'Cartões', path: '/cards' },
      { name: 'Investimentos', path: '/investments' },
      { name: 'Previdência', path: '/pension' },
      { name: 'Assinaturas', path: '/subscriptions' },
      { name: 'Categorização', path: '/rules' },
      { name: 'Revisão mensal', path: '/monthly-review' },
      { name: 'Diagnóstico', path: '/health-score' },
      { name: 'Construtor de portfólio', path: '/portfolio-builder' },
      { name: 'Otimizador', path: '/optimizer' },
      { name: 'Simulador', path: '/simulator' },
      { name: 'Relatório IA', path: '/ai-report' },
      { name: 'Chat IA', path: '/chat' },
      { name: 'Relatório executivo', path: '/executive-report' },
    ],
  },
]
</script>
