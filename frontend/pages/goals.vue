<script setup lang="ts">
const { goals, refresh } = useGoals()
</script>

<template>
  <section class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold">Metas Financeiras</h1>
        <p class="mt-1 text-slate-600">Defina e acompanhe suas metas de planejamento financeiro.</p>
      </div>
      <goals-create-goal-modal @created="refresh" />
    </div>

    <div v-if="!goals?.length" class="rounded-lg border border-dashed border-slate-300 p-8 text-center">
      <Icon icon="mdi:flag-outline" class="mx-auto mb-3 h-10 w-10 text-slate-300" />
      <p class="text-slate-500">Nenhuma meta definida ainda.</p>
      <p class="mt-1 text-sm text-slate-400">Crie sua primeira meta para começar a acompanhar seu progresso.</p>
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2">
      <goals-goal-card v-for="goal in goals" :key="goal.id" :goal="goal" />
    </div>
  </section>
</template>
