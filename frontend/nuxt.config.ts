export default defineNuxtConfig({
  devtools: { enabled: true },
  css: ["~/assets/css/tailwind.css", "primeicons/primeicons.css"],
  modules: ["@nuxtjs/tailwindcss", "@pinia/nuxt", "@nuxtjs/apollo"],
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1",
      graphqlEndpoint: process.env.NUXT_PUBLIC_GRAPHQL_ENDPOINT || "http://localhost:8000/graphql/",
      pluggyConnectUrl: process.env.NUXT_PUBLIC_PLUGGY_CONNECT_URL || "https://connect.pluggy.ai"
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
