// Formatação de data no padrão ISO (YYYY-MM-DD) em toda a aplicação, em vez de
// pt-BR (DD/MM/YYYY). Duas funções porque a origem importa:
//
// - Campo só-data (due_date, paid_date, target_date, as_of_date): a string já é
//   "YYYY-MM-DD" sem hora/fuso. `new Date('2026-08-10')` é parseado como UTC
//   meia-noite, e em America/Sao_Paulo (UTC-3) isso renderiza um dia antes —
//   `formatIsoDate` recorta a string em vez de passar por `Date`.
// - Datetime completo (created_at, booked_at, started_at...): a string já carrega
//   o fuso (offset ou "Z"), então o parse via `Date` é seguro; só a formatação
//   troca de pt-BR para ISO.

const pad = (value: number): string => String(value).padStart(2, '0')

export function formatIsoDate(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(0, 10)
}

export function formatIsoDateOnly(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function formatIsoDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  return `${formatIsoDateOnly(value)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Sentido contrário de `formatIsoDateOnly`: um `Date` (ex.: saída de um
// `DatePicker` do PrimeVue, que trabalha em `Date`, não em string) de volta
// para "YYYY-MM-DD" -- formato que o backend, a exportação CSV e a
// localStorage dos filtros esperam.
export function toIsoDateString(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
