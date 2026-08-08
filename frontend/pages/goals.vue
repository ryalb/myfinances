<script setup lang="ts">
definePageMeta({
  middleware: 'auth',
})

const { goals, refresh } = useGoals()
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Metas Financeiras</h1>
        <p class="mt-1 text-sepia-600">Defina e acompanhe suas metas de planejamento financeiro.</p>
      </div>
      <goals-create-goal-modal @created="refresh" />
    </div>

    <div v-if="!goals?.length" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:flag-outline" class="mx-auto mb-3 h-10 w-10 text-sepia-300" />
      <p class="text-sepia-500">Nenhuma meta definida ainda.</p>
      <p class="mt-1 text-sm text-sepia-400">Crie sua primeira meta para começar a acompanhar seu progresso.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <goals-goal-card v-for="goal in goals" :key="goal.id" :goal="goal" />
    </div>
  </section>
</template>
