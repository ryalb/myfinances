<script setup lang="ts">
import { Icon } from '@iconify/vue'

definePageMeta({
  middleware: 'auth',
})
</script>

<template>
  <section class="space-y-8">
    <div class="space-y-4">
      <h1 class="flex items-center gap-3 text-4xl font-bold">
        <Icon icon="mdi:chart-line" class="text-emerald-600" />
        MyFinances
      </h1>
      <p class="max-w-2xl text-lg text-sepia-600">
        Consolide sua vida financeira em um só lugar. Conecte suas instituições, acompanhe seu patrimônio e planeje sua
        liberdade financeira.
      </p>
    </div>

    <!-- Feature cards -->
    <div class="grid gap-4 md:grid-cols-3">
      <NuxtLink to="/integrations" class="rounded-xl border border-sepia-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
        <Icon icon="mdi:link-variant" class="mb-3 h-8 w-8 text-sepia-500" />
        <h3 class="font-semibold text-sepia-900">Conecte suas contas</h3>
        <p class="mt-2 text-sm text-sepia-500">Integre bancos e corretoras via Pluggy de forma segura.</p>
      </NuxtLink>

      <NuxtLink to="/dashboard" class="rounded-xl border border-sepia-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
        <Icon icon="mdi:chart-bar" class="mb-3 h-8 w-8 text-emerald-600" />
        <h3 class="font-semibold text-sepia-900">Acompanhe seu patrimônio</h3>
        <p class="mt-2 text-sm text-sepia-500">Visualize saldos, transações e evolução patrimonial.</p>
      </NuxtLink>

      <NuxtLink to="/goals" class="rounded-xl border border-sepia-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
        <Icon icon="mdi:flag-outline" class="mb-3 h-8 w-8 text-sepia-600" />
        <h3 class="font-semibold text-sepia-900">Planeje sua liberdade</h3>
        <p class="mt-2 text-sm text-sepia-500">Defina metas e acompanhe o caminho até a independência financeira.</p>
      </NuxtLink>
    </div>

    <div class="flex gap-3">
      <NuxtLink
        to="/dashboard"
        class="inline-flex items-center gap-2 rounded-lg bg-sepia-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-sepia-700"
      >
        <Icon icon="mdi:arrow-right" class="h-4 w-4" />
        Abrir dashboard
      </NuxtLink>
      <NuxtLink
        to="/integrations"
        class="inline-flex items-center gap-2 rounded-lg border border-sepia-300 px-5 py-2.5 text-sm font-medium text-sepia-700 hover:bg-sepia-50"
      >
        <Icon icon="mdi:link-plus" class="h-4 w-4" />
        Conectar instituição
      </NuxtLink>
    </div>
  </section>
</template>
