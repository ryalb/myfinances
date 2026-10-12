export default defineNuxtConfig({
  devtools: { enabled: true },
  compatibilityDate: '2026-08-07',
  css: ["~/assets/css/tailwind.css", "~/assets/css/theme.css", "primeicons/primeicons.css"],
  modules: ["@nuxtjs/tailwindcss", "@pinia/nuxt", "@nuxtjs/apollo"],
  ssr: false,
  // Web components do ldrs (`<l-quantum>` etc., ver plugins/ldrs.client.ts):
  // sem isso o Vue tenta resolver a tag como componente e avisa no console.
  vue: {
    compilerOptions: {
      isCustomElement: (tag) => tag.startsWith('l-'),
    },
  },
  app: {
    head: {
      link: [
        { rel: "icon", type: "image/png", href: "/logo.png" },
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "anonymous" },
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap",
        },
      ],
    },
  },
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1",
      graphqlEndpoint: process.env.NUXT_PUBLIC_GRAPHQL_ENDPOINT || "http://localhost:8000/graphql/",
    }
  },
  apollo: {
    clients: {
      default: {
        httpEndpoint: process.env.NUXT_PUBLIC_GRAPHQL_ENDPOINT || "http://localhost:8000/graphql/"
      }
    }
  }
})
