<template>
  <header
    class="sticky top-0 flex w-full bg-sepia-50 border-sepia-200 z-99999 border-b"
  >
    <div class="flex flex-col items-center justify-between grow lg:flex-row lg:px-6">
      <div
        class="flex items-center justify-between w-full gap-2 px-3 py-3 border-b border-sepia-200 sm:gap-4 lg:justify-normal lg:border-b-0 lg:px-0 lg:py-4"
      >
        <button
          type="button"
          class="flex items-center justify-center w-10 h-10 text-sepia-500 border border-sepia-200 rounded-lg lg:w-11 lg:h-11 hover:bg-sepia-100"
          @click="handleToggle"
        >
          <svg
            v-if="isMobileOpen"
            class="fill-current"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M6.21967 7.28131C5.92678 6.98841 5.92678 6.51354 6.21967 6.22065C6.51256 5.92775 6.98744 5.92775 7.28033 6.22065L11.999 10.9393L16.7176 6.22078C17.0105 5.92789 17.4854 5.92788 17.7782 6.22078C18.0711 6.51367 18.0711 6.98855 17.7782 7.28144L13.0597 12L17.7782 16.7186C18.0711 17.0115 18.0711 17.4863 17.7782 17.7792C17.4854 18.0721 17.4854 18.0721 17.7782 17.7792L11.999 13.0607L7.28033 17.7794C6.98744 18.0722 6.98744 18.0722 6.21967 17.7794C5.92678 17.4865 5.92678 17.0116 6.21967 16.7187L10.9384 12L6.21967 7.28131Z"
              fill="none"
            />
          </svg>
          <svg
            v-else
            width="16"
            height="12"
            viewBox="0 0 16 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M0.583252 1C0.583252 0.585788 0.919038 0.25 1.33325 0.25H14.6666C15.0808 0.25 15.4166 0.585786 15.4166 1C15.4166 1.41421 15.0808 0.919038 14.6666 1.75C0.919038 1.75 0.583252 1.41422 0.583252 1ZM0.583252 11C0.583252 10.5858 0.919038 10.25 1.33325 10.25L14.6666 10.25C15.0808 10.25 15.4166 10.5858 15.4166 11C15.4166 11.4142 15.0808 11.75 14.6666 11.75L1.33325 11.75C0.583252 11.75 0.583252 11.4142 0.583252 11ZM1.33325 5.25C0.919038 5.25 0.583252 5.58579 0.583252 6C0.583252 6.41421 0.919038 6.75 1.33325 6.75L7.99992 6.75C8.41413 6.75 8.74992 6.41421 8.74992 6C8.74992 5.58579 8.41413 5.25 7.99992 5.25L1.33325 5.25Z"
              fill="currentColor"
            />
          </svg>
        </button>
        <NuxtLink to="/dashboard" class="hidden lg:flex items-center gap-3 text-lg font-semibold text-sepia-900">
          <img src="/logo.png" alt="MyFinances" class="h-8 w-auto">
          <span>MyFinances</span>
        </NuxtLink>
        <button
          type="button"
          class="flex items-center justify-center w-10 h-10 text-sepia-700 rounded-lg hover:bg-sepia-100 lg:hidden"
          @click="toggleApplicationMenu"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M5.99902 10.4951C6.82745 10.4951 7.49902 11.1667 7.49902 11.9951V12.0051C7.49902 12.8335 6.82745 13.5051 5.99902 13.5051C5.1706 13.5051 4.49902 12.8335 4.49902 12.0051V11.9951C4.49902 11.1667 5.1706 10.4951 5.99902 10.4951Z"
              fill="currentColor"
            />
          </svg>
        </button>
      </div>

      <div
        :class="[isApplicationMenuOpen ? 'flex' : 'hidden']"
        class="items-center justify-between w-full gap-4 px-5 py-4 lg:flex lg:justify-end lg:px-0"
      >
        <div class="flex items-center gap-2 2xsm:gap-3">
          <!-- Central de alertas: derivados do estado atual, então desaparecem
               quando a condição se resolve. -->
          <div class="relative">
            <button
              type="button"
              class="relative flex items-center justify-center w-10 h-10 text-sepia-700 rounded-lg hover:bg-sepia-100"
              :title="count ? `${count} alerta(s)` : 'Nenhum alerta'"
              @click="alertsOpen = !alertsOpen"
            >
              <Icon icon="mdi:bell-outline" class="h-5 w-5" />
              <span
                v-if="actionableCount"
                class="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white"
              >
                {{ actionableCount }}
              </span>
              <span
                v-else-if="count"
                class="absolute right-2 top-2 h-2 w-2 rounded-full bg-sepia-400"
              />
            </button>

            <div
              v-if="alertsOpen"
              class="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-sepia-200 bg-white p-2 shadow-lg"
            >
              <p v-if="!count" class="px-3 py-6 text-center text-sm text-sepia-400">
                Nada precisa da sua atenção agora.
              </p>
              <ul v-else class="space-y-1">
                <li v-for="alert in alerts" :key="alert.kind">
                  <NuxtLink
                    :to="alert.actionPath"
                    class="flex gap-2 rounded-lg px-3 py-2 hover:bg-sepia-50"
                    @click="alertsOpen = false"
                  >
                    <Icon
                      :icon="ALERT_STYLES[alert.severity].icon"
                      :class="['mt-0.5 h-4 w-4 shrink-0', alert.severity === 'danger' ? 'text-rose-600' : alert.severity === 'warning' ? 'text-amber-600' : 'text-sepia-400']"
                    />
                    <span class="min-w-0">
                      <span class="block text-sm font-medium text-sepia-900">{{ alert.title }}</span>
                      <span class="block text-xs text-sepia-500">{{ alert.detail }}</span>
                    </span>
                  </NuxtLink>
                </li>
              </ul>
            </div>
          </div>

          <button
            type="button"
            class="flex items-center justify-center w-10 h-10 text-sepia-700 rounded-lg hover:bg-sepia-100"
            :title="uiStore.isFinancialValueBlurred ? 'Mostrar valores' : 'Ocultar valores'"
            @click="toggleFinancialValueBlur"
          >
            <Icon :icon="uiStore.isFinancialValueBlurred ? 'mdi:eye-off' : 'mdi:eye'" class="h-5 w-5" />
          </button>
          <button
            type="button"
            class="flex items-center gap-2 px-3 py-2 text-sepia-700 rounded-lg hover:bg-sepia-100"
            @click="handleLogout"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
            <span>Sair</span>
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSidebar } from '@/composables/useSidebar'
import { useAuth } from '@/composables/useAuth'
import { useRouter } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { ALERT_STYLES } from '@/composables/useAlerts'

const { toggleSidebar, toggleMobileSidebar, isMobileOpen } = useSidebar()
const { logout } = useAuth()
const router = useRouter()
const uiStore = useUiStore()

const { alerts, count, actionableCount } = useAlerts()
const alertsOpen = ref(false)

const handleToggle = () => {
  if (window.innerWidth >= 1024) {
    toggleSidebar()
  } else {
    toggleMobileSidebar()
  }
}

const isApplicationMenuOpen = ref(false)

const toggleApplicationMenu = () => {
  isApplicationMenuOpen.value = !isApplicationMenuOpen.value
}

const toggleFinancialValueBlur = () => {
  uiStore.toggleFinancialValueBlur()
}

const handleLogout = () => {
  logout()
  router.push('/login')
}
</script>
