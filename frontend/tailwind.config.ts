import type { Config } from "tailwindcss"

export default {
  content: [
    "./components/**/*.{js,vue,ts}",
    "./layouts/**/*.vue",
    "./pages/**/*.vue",
    "./plugins/**/*.{js,ts}",
    "./app.vue"
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#faf6f1',
          100: '#f0e6d8',
          200: '#e0ccb0',
          300: '#c4a882',
          400: '#a68b64',
          500: '#8b7355',
          600: '#6b5a45',
          700: '#4a3c2e',
          800: '#332a20',
          900: '#1f1a14',
          950: '#14110c',
        },
        sepia: {
          50: '#faf6f1',
          100: '#f0e6d8',
          200: '#e0ccb0',
          300: '#c4a882',
          400: '#a68b64',
          500: '#8b7355',
          600: '#6b5a45',
          700: '#4a3c2e',
          800: '#332a20',
          900: '#1f1a14',
          950: '#14110c',
        }
      },
      boxShadow: {
        'theme-sm': '0px 1px 3px 0px rgba(16, 24, 40, 0.1), 0px 1px 2px 0px rgba(16, 24, 40, 0.06)',
        'theme-md': '0px 4px 8px -2px rgba(16, 24, 40, 0.1), 0px 2px 4px -2px rgba(16, 24, 40, 0.06)',
        'theme-lg': '0px 12px 16px -4px rgba(16, 24, 40, 0.08), 0px 4px 6px -2px rgba(16, 24, 40, 0.03)',
        'theme-xl': '0px 20px 24px -4px rgba(16, 24, 40, 0.08), 0px 8px 8px -4px rgba(16, 24, 40, 0.03)',
      },
      zIndex: {
        '1': 1,
        '9': 9,
        '99': 99,
        '999': 999,
        '9999': 9999,
        '99999': 99999,
      },
      screens: {
        '2xsm': '375px',
        'xsm': '425px',
        'sm': '640px',
        'md': '768px',
        'lg': '1024px',
        'xl': '1280px',
        '2xl': '1536px',
        '3xl': '2000px',
      }
    }
  },
  plugins: []
} satisfies Config
