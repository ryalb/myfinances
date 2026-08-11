// Rótulos compartilhados entre a página /subscriptions e o card do dashboard.
// Duplicar os mapas nos dois lugares faria as listas divergirem quando uma
// categoria nova entrasse em SubscriptionCategory.

import { formatIsoDate } from '@/composables/useDateFormat'

export const SUBSCRIPTION_CATEGORY_LABELS: Record<string, string> = {
  utilities: 'Utilidades',
  internet: 'Internet',
  phone: 'Telefone',
  streaming: 'Streaming',
  other: 'Outro',
}

// Ordem de exibição no formulário. Derivada do mapa acima para não divergir dele.
export const SUBSCRIPTION_CATEGORY_OPTIONS = Object.entries(SUBSCRIPTION_CATEGORY_LABELS).map(
  ([value, label]) => ({ value, label }),
)

export const SUBSCRIPTION_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: 'Pendente', color: 'bg-amber-100 text-amber-700' },
  paid: { label: 'Pago', color: 'bg-emerald-100 text-emerald-700' },
  overdue: { label: 'Atrasado', color: 'bg-rose-100 text-rose-700' },
}

export function useSubscriptionLabels() {
  const categoryLabel = (category: string) => SUBSCRIPTION_CATEGORY_LABELS[category] || category

  const statusBadge = (status: string) =>
    SUBSCRIPTION_STATUS_LABELS[status] || { label: status, color: 'bg-sepia-100 text-sepia-600' }

  const formatDueDate = (isoDate: string) => formatIsoDate(isoDate)

  return { categoryLabel, statusBadge, formatDueDate }
}
