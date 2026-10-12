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
                     <svg v-else-if="item.path === '/chat'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                     <svg v-else-if="item.path === '/rules'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/></svg>
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
                  <button
                    v-if="item.path === '/investments' && investmentCategories.length && (isExpanded || isHovered || isMobileOpen)"
                    type="button"
                    class="ml-auto rounded p-0.5 text-sepia-400 hover:text-sepia-100"
                    :aria-label="investmentsMenuOpen ? 'Recolher categorias' : 'Mostrar categorias'"
                    :aria-expanded="investmentsMenuOpen"
                    @click.prevent.stop="investmentsMenuOpen = !investmentsMenuOpen"
                  >
                    <Icon :icon="investmentsMenuOpen ? 'mdi:chevron-up' : 'mdi:chevron-down'" class="h-4 w-4" />
                  </button>
                </NuxtLink>
                <ul
                  v-if="item.path === '/investments' && investmentsMenuOpen && (isExpanded || isHovered || isMobileOpen)"
                  class="ml-5 mt-1 flex flex-col gap-0.5 border-l border-sepia-800 pl-3"
                >
                  <li v-for="category in investmentCategories" :key="category.key">
                    <NuxtLink
                      :to="`/investments/${category.key}`"
                      :class="[
                        'block rounded-md px-2 py-1.5 text-[13px] transition-colors',
                        route.path === `/investments/${category.key}`
                          ? 'bg-sepia-900 text-sepia-50'
                          : 'text-sepia-400 hover:bg-sepia-900/60 hover:text-sepia-50',
                      ]"
                    >
                      {{ category.label }}
                    </NuxtLink>
                  </li>
                </ul>
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
import { computed, onMounted, ref, watch } from 'vue'
import { compareCategoryKeys, useInvestmentList } from '@/composables/useInvestments'

const route = useRoute()
const { isExpanded, isMobileOpen, isHovered } = useSidebar()
const currentUser = useCurrentUser()
const avatarLoadFailed = ref(false)

// Prefixo, nao igualdade: `/investments/fii` mantem "Investimentos" ativo.
const isActive = (path: string) => route.path === path || route.path.startsWith(`${path}/`)

// Submenu de Investimentos: uma entrada por categoria que o usuario de fato
// tem (mesmas chaves de `display_category` das subpaginas /investments/<chave>).
const { data: investmentList } = useInvestmentList()
const investmentCategories = computed(() => {
  const byKey = new Map<string, string>()
  for (const investment of investmentList.value || []) {
    byKey.set(investment.display_category, investment.display_category_label)
  }
  return Array.from(byKey, ([key, label]) => ({ key, label })).sort((a, b) => compareCategoryKeys(a.key, b.key))
})

// Abre sozinho ao entrar em qualquer tela de investimentos; fora delas, so
// pelo botao, para nao empurrar o resto do menu para baixo.
const investmentsMenuOpen = ref(isActive('/investments'))
watch(
  () => route.path,
  () => {
    if (isActive('/investments')) investmentsMenuOpen.value = true
  },
)

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
      { name: 'Chat IA', path: '/chat' },
    ],
  },
]
</script>
