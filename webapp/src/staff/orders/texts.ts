import type { StaffOrder } from '../../api/types'

export const clock = new Intl.DateTimeFormat('ru-RU', { hour: 'numeric', minute: '2-digit' })

export type Column = 'new' | 'cooking' | 'ready' | 'delivering' | 'scheduled'

export const COLUMNS: { id: Column; label: string; statuses: string[] }[] = [
  { id: 'new', label: 'Новые', statuses: ['new'] },
  { id: 'cooking', label: 'Готовятся', statuses: ['accepted', 'cooking'] },
  { id: 'ready', label: 'Готовы', statuses: ['ready'] },
  { id: 'delivering', label: 'В доставке', statuses: ['delivering'] },
  { id: 'scheduled', label: 'Запланированные', statuses: ['scheduled'] },
]

export const LOAD_LABELS: Record<string, string> = { calm: 'спокойно', moderate: 'умеренно', busy: 'загружены' }

export function nextStep(order: StaffOrder): { action: string; label: string } | undefined {
  if (order.status === 'ready' && order.fulfilment === 'delivery') return { action: 'dispatch', label: 'Передан курьеру' }
  if (order.status === 'delivering') return { action: 'deliver', label: 'Доставлен' }
  return NEXT_STEP[order.status]
}

export function addressLine(order: StaffOrder): string | null {
  const a = order.address
  if (!a) return null
  const parts = [`корп. ${a.house}`, `кв. ${a.apartment}`]
  if (a.entrance) parts.push(`под. ${a.entrance}`)
  if (a.floor) parts.push(`эт. ${a.floor}`)
  if (a.comment) parts.push(a.comment)
  return parts.join(', ')
}

export const STATUS_LABELS: Record<string, string> = {
  pending_payment: 'Ждёт оплату',
  scheduled: 'Запланирован',
  new: 'Новый',
  accepted: 'Принят',
  cooking: 'Готовится',
  ready: 'Готов',
  handed_over: 'Выдан',
  delivering: 'В доставке',
  delivered: 'Доставлен',
  cancelled: 'Отменён',
}

/** The one main next step on a card (EXPERIENCE.md › staff card). */
export const NEXT_STEP: Record<string, { action: string; label: string } | undefined> = {
  new: { action: 'accept', label: 'Принять' },
  accepted: { action: 'start_cooking', label: 'Готовится' },
  cooking: { action: 'mark_ready', label: 'Готов' },
  ready: { action: 'hand_over', label: 'Выдан' },
}

export const ACTION_LABELS: Record<string, string> = {
  create: 'Оформлен',
  payment_succeeded: 'Оплачен онлайн',
  release: 'Передан на кухню',
  accept: 'Принят',
  start_cooking: 'Готовится',
  mark_ready: 'Готов',
  hand_over: 'Выдан',
  dispatch: 'Передан курьеру',
  deliver: 'Доставлен',
  cancel: 'Отменён',
}

export const CANCEL_REASONS = ['Нет продуктов', 'Не успеваем', 'Гость попросил']

export function paymentBadge(order: StaffOrder): { text: string; paid: boolean } {
  if (order.payment_status === 'paid') {
    const how = order.paid_with === 'online' ? 'онлайн' : order.paid_with === 'cash' ? 'наличными' : 'картой'
    return { text: `Оплачен ${how}`, paid: true }
  }
  if (order.payment_status === 'refunded') return { text: 'Деньги возвращены', paid: false }
  const how = order.payment_method === 'cash' ? 'наличными' : order.payment_method === 'card' ? 'картой' : 'онлайн'
  return { text: `Не оплачен · ${how}`, paid: false }
}
