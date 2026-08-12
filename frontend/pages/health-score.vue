<script setup lang="ts">
definePageMeta({
  middleware: 'auth',
})

const { healthScore } = useFinancialHealthScore()

const scoreTone = (score: number) => (score >= 80 ? 'azul' : score >= 50 ? 'amber' : 'vermelho')

const scoreToneClasses: Record<string, string> = {
  azul: 'text-azul-600',
  amber: 'text-amber-600',
  vermelho: 'text-vermelho-600',
}

const barToneClasses: Record<string, string> = {
  azul: 'bg-azul-600',
  amber: 'bg-amber-500',
  vermelho: 'bg-vermelho-600',
}

const overallTone = computed(() => scoreTone(healthScore.value?.score ?? 0))

const scoreLabel = computed(() => {
  const score = healthScore.value?.score ?? 0
  if (score >= 80) return 'Saudável'
  if (score >= 50) return 'Atenção'
  return 'Crítico'
})
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold">Diagnóstico de saúde financeira</h1>
      <p class="mt-1 text-sepia-600">
        Uma nota de 0 a 100 combinando poupança, reserva, uso do crédito, tendência de patrimônio
        e alertas ativos — recalculada a cada visita, nunca guardada.
      </p>
    </div>

    <div v-if="!healthScore" class="rounded-lg border border-dashed border-sepia-300 p-8 text-center">
      <Icon icon="mdi:loading" class="mx-auto mb-3 h-8 w-8 animate-spin text-sepia-400" />
      <p class="text-sepia-500">Calculando o diagnóstico...</p>
    </div>

    <template v-else>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <article class="rounded-lg border border-sepia-200 bg-white p-6 text-center shadow-sm md:col-span-1">
          <p class="text-xs font-medium uppercase tracking-wide text-sepia-400">Nota geral</p>
          <p :class="['mt-2 font-mono text-5xl font-bold', scoreToneClasses[overallTone]]">
            {{ healthScore.score.toFixed(0) }}
          </p>
          <p :class="['mt-1 text-sm font-medium', scoreToneClasses[overallTone]]">{{ scoreLabel }}</p>
        </article>

        <article class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm md:col-span-2">
          <h3 class="mb-3 flex items-center gap-2 text-base font-semibold text-sepia-900">
            <Icon icon="mdi:lightbulb-on-outline" class="h-5 w-5 text-azul-600" />
            As 3 ações que mais ajudariam
          </h3>
          <ul v-if="healthScore.topActions.length" class="space-y-2">
            <li v-for="(action, idx) in healthScore.topActions" :key="idx" class="flex gap-2 text-sm text-sepia-700">
              <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sepia-100 text-xs font-semibold text-sepia-600">
                {{ idx + 1 }}
              </span>
              <span>{{ action }}</span>
            </li>
          </ul>
          <p v-else class="text-sm text-sepia-400">
            Todos os componentes estão na nota máxima. Nada para ajustar agora.
          </p>
        </article>
      </div>

      <div class="rounded-lg border border-sepia-200 bg-white p-5 shadow-sm">
        <h3 class="mb-3 text-base font-semibold text-sepia-900">Componentes</h3>
        <div class="space-y-4">
          <div v-for="component in healthScore.components" :key="component.key">
            <div class="mb-1 flex items-center justify-between">
              <span class="text-sm font-medium text-sepia-900">
                {{ component.label }}
                <span class="text-xs font-normal text-sepia-400">(peso {{ component.weight.toFixed(0) }}%)</span>
              </span>
              <span :class="['font-mono text-sm', scoreToneClasses[scoreTone(component.score)]]">
                {{ component.score.toFixed(0) }}
              </span>
            </div>
            <div class="h-2 w-full rounded-full bg-sepia-100">
              <div
                :class="['h-2 rounded-full transition-all', barToneClasses[scoreTone(component.score)]]"
                :style="{ width: `${component.score}%` }"
              />
            </div>
            <p class="mt-1 text-xs text-sepia-500">{{ component.detail }}</p>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>
