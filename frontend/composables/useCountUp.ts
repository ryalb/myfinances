/**
 * Efeito "tally": conta de zero até o valor final, como um totalizador
 * mecânico. Usado uma única vez, no número de maior destaque do dashboard —
 * não em cada card, para não virar ruído.
 */
export const useCountUp = (target: number, durationMs = 900) => {
  const value = ref(0)

  onMounted(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion || !target) {
      value.value = target
      return
    }

    const start = performance.now()

    const tick = (now: number) => {
      const progress = Math.min((now - start) / durationMs, 1)
      const eased = 1 - (1 - progress) ** 3
      value.value = target * eased
      if (progress < 1) requestAnimationFrame(tick)
    }

    requestAnimationFrame(tick)
  })

  return value
}
