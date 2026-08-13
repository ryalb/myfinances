export const formatBRL = (v: number | string | null | undefined): string => {
  if (v === null || v === undefined || v === '') return 'R$ 0,00'
  return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

// `signed` força o "+" em valores positivos (rendimento, desvio de meta) --
// sem isso um 12,3% de rentabilidade e um -12,3% ficam visualmente parecidos
// demais numa coluna de tabela.
export const formatPercent = (
  v: number | string | null | undefined,
  { signed = false }: { signed?: boolean } = {},
): string => {
  if (v === null || v === undefined || v === '') return '—'
  const value = Number(v)
  const formatted = value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return signed && value > 0 ? `+${formatted}%` : `${formatted}%`
}
