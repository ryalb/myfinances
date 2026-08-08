export const formatBRL = (v: number | string | null | undefined): string => {
  if (v === null || v === undefined || v === '') return 'R$ 0,00'
  return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}
