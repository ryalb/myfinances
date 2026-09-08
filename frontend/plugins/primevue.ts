import Aura from "@primeuix/themes/aura"
import { definePreset } from "@primeuix/themes"
import PrimeVue from "primevue/config"

// Mesma escala do `sepia` em tailwind.config.ts. O Aura usa `primary` para
// preencher botão, foco, seleção e destaque; sem sobrescrever, tudo isso sai no
// emerald default dele e briga com o tema.
const SEPIA = {
  50: "#fbf7ee",
  100: "#f5eedd",
  200: "#e7d9b8",
  300: "#cfb683",
  400: "#ad8a54",
  500: "#85652f",
  600: "#6b4f26",
  700: "#4e3a1d",
  800: "#33261a",
  900: "#241b10",
  950: "#160f09",
}

const SepiaAura = definePreset(Aura, {
  semantic: {
    primary: SEPIA,
    // `primary` sozinho não alcança overlay (Popover, dropdown, tooltip): esses
    // usam o grupo semântico `overlay`, com token próprio por componente
    // (`overlay.popover.*` etc.), então saíam no cinza generico do Aura mesmo
    // com `primary` já sepia. Alinhado ao cartão branco padrão do app
    // (`bg-white border-sepia-200 shadow-sm rounded-lg`).
    overlay: {
      popover: {
        background: "#ffffff",
        borderColor: SEPIA[200],
        color: SEPIA[800],
        borderRadius: "0.5rem",
        shadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      },
    },
  },
})

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.use(PrimeVue, {
    theme: {
      preset: SepiaAura,
      options: {
        // `darkModeSelector` default do Aura é `"system"`, que resolve para
        // `@media (prefers-color-scheme: dark)`. Com o SO em modo escuro o Aura
        // emitia `color-scheme: dark` no `:root` — e é `color-scheme` que faz o
        // navegador desenhar controle nativo (`<input>`, `<select>`) com o estilo
        // escuro do sistema. O resultado era input preto numa página clara.
        //
        // O app é claro por design (`body` fixo em #faf6f1 no theme.css), então
        // seguir o SO nunca foi a intenção. `false` desliga o esquema escuro.
        darkModeSelector: false,
      },
    },
  })
})
