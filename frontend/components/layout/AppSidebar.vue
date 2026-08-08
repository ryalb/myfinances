<template>
  <aside
    :class="[
      'fixed mt-16 flex flex-col lg:mt-0 top-0 px-5 left-0 bg-sepia-50 text-sepia-900 h-screen transition-all duration-300 ease-in-out z-99999 border-r border-sepia-200',
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
        'py-6 flex',
        !isExpanded && !isHovered ? 'lg:justify-center' : 'justify-start',
      ]"
    >
      <NuxtLink to="/" class="flex items-center gap-3">
        <img v-if="isExpanded || isHovered || isMobileOpen" src="/logo.png" alt="MyFinances" class="h-8 w-auto">
        <img v-else src="/logo.png" alt="MF" class="h-8 w-auto">
        <span v-if="isExpanded || isHovered || isMobileOpen" class="text-lg font-semibold text-sepia-900 whitespace-nowrap">MyFinances</span>
      </NuxtLink>
    </div>
    <div
      class="flex-1 flex flex-col overflow-y-auto p-1 duration-300 ease-linear no-scrollbar"
    >
      <nav class="mb-6">
        <div class="flex flex-col gap-4">
          <div v-for="(menuGroup, groupIndex) in menuGroups" :key="groupIndex">
            <h2
              v-if="isExpanded || isHovered || isMobileOpen"
              class="mb-4 text-xs uppercase flex leading-[20px] text-sepia-400"
            >
              {{ menuGroup.title }}
            </h2>
            <ul class="flex flex-col gap-4">
              <li v-for="item in menuGroup.items" :key="item.name">
                <NuxtLink
                  v-if="item.path"
                  :to="item.path"
                  :class="[
                    'menu-item group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                    isActive(item.path)
                      ? 'bg-sepia-50 text-sepia-600'
                      : 'text-sepia-700 hover:bg-sepia-100',
                  ]"
                >
                  <span
                    :class="[
                      'flex h-10 w-10 items-center justify-center rounded-lg',
                      isActive(item.path)
                        ? 'bg-sepia-100 text-sepia-600'
                        : 'bg-sepia-100 text-sepia-600',
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
    <div class="mt-auto border-t border-sepia-200 py-4">
      <div
        :class="[
          'flex items-center gap-3',
          !isExpanded && !isHovered && !isMobileOpen ? 'lg:justify-center' : 'justify-start',
        ]"
      >
        <Avatar
          v-if="currentUser.user"
          :image="currentUser.gravatarUrl"
          :label="currentUser.initials"
          size="large"
          shape="circle"
          class="!bg-sepia-200 !text-sepia-700"
        />
        <div
          v-if="currentUser.user && (isExpanded || isHovered || isMobileOpen)"
          class="flex flex-col"
        >
          <span class="text-sm font-medium text-sepia-900">{{ currentUser.fullName }}</span>
          <span class="text-xs text-sepia-500">{{ currentUser.user.email }}</span>
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
import { onMounted } from 'vue'

const route = useRoute()
const { isExpanded, isMobileOpen, isHovered } = useSidebar()
const currentUser = useCurrentUser()

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
      { name: 'Relatório IA', path: '/ai-report' },
    ],
  },
]
</script>
