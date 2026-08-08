export default defineNuxtConfig({
  devtools: { enabled: true },
  compatibilityDate: '2026-08-07',
  css: ["~/assets/css/tailwind.css", "~/assets/css/theme.css", "primeicons/primeicons.css"],
  modules: ["@nuxtjs/tailwindcss", "@pinia/nuxt", "@nuxtjs/apollo"],
  ssr: false,
  app: {
    head: {
      link: [
        { rel: "icon", type: "image/png", href: "/logo.png" },
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
