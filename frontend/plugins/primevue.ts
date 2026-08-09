import Aura from "@primeuix/themes/aura"
import { definePreset } from "@primeuix/themes"
import PrimeVue from "primevue/config"

// Mesma escala do `sepia` em tailwind.config.ts. O Aura usa `primary` para
// preencher botão, foco, seleção e destaque; sem sobrescrever, tudo isso sai no
// emerald default dele e briga com o tema.
const SEPIA = {
  50: "#faf6f1",
  100: "#f0e6d8",
  200: "#e0ccb0",
  300: "#c4a882",
  400: "#a68b64",
  500: "#8b7355",
  600: "#6b5a45",
  700: "#4a3c2e",
  800: "#332a20",
  900: "#1f1a14",
  950: "#14110c",
}

const SepiaAura = definePreset(Aura, {
  semantic: {
    primary: SEPIA,
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
