import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    isFinancialValueBlurred: typeof window !== 'undefined' ? localStorage.getItem('financialValueBlurred') !== 'false' : true,
  }),
  actions: {
    toggleFinancialValueBlur() {
      this.isFinancialValueBlurred = !this.isFinancialValueBlurred
      if (typeof window !== 'undefined') {
        localStorage.setItem('financialValueBlurred', String(this.isFinancialValueBlurred))
      }
    },
  },
})
