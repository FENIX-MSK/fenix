import type { Order } from '../api/types'

// Guest-facing wording of the order lifecycle (EXPERIENCE.md › Voice and Tone).
export const STATUS_LABELS: Record<string, string> = {
  pending_payment: 'Ждём оплату',
  scheduled: 'Запланирован',
  new: 'Отправлен в кафе',
  accepted: 'Принят',
  cooking: 'Готовится',
  ready: 'Готов — ждём вас у кассы',
  handed_over: 'Выдан',
  delivering: 'Уже едет к вам',
  delivered: 'Доставлен',
  cancelled: 'Отменён',
}

export const PAYMENT_LABELS: Record<string, string> = {
  online: 'Онлайн',
  cash: 'Наличными на кассе',
  card: 'Картой на кассе',
}

export const FULFILMENT_LABELS: Record<string, string> = {
  pickup: 'Самовывоз',
  delivery: 'Доставка',
}

const clock = new Intl.DateTimeFormat('ru-RU', { hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Moscow' })

export function addressText(order: Order): string | null {
  const a = order.address
  if (!a) return null
  const parts = [`корпус ${a.house}`, `кв. ${a.apartment}`]
  if (a.entrance) parts.push(`подъезд ${a.entrance}`)
  if (a.floor) parts.push(`этаж ${a.floor}`)
  return parts.join(', ')
}

export function scheduledText(order: Order): string | null {
  return order.scheduled_for ? `к ${clock.format(new Date(order.scheduled_for))}` : null
}

export function paymentText(order: Order): string {
  if (order.payment_status === 'paid') return `${PAYMENT_LABELS[order.payment_method]} · оплачен`
  if (order.payment_status === 'refunded') return `${PAYMENT_LABELS[order.payment_method]} · деньги возвращены`
  return PAYMENT_LABELS[order.payment_method] ?? order.payment_method
}

/** Why the order was not created, by the server's error code. */
const slotTime = new Intl.DateTimeFormat('ru-RU', { hour: 'numeric', minute: '2-digit', timeZone: 'Europe/Moscow' })

export function orderErrorText(code: string | undefined, details?: Record<string, unknown>): string {
  switch (code) {
    case 'slot_unavailable': {
      const slots = (details?.slots as string[] | undefined) ?? []
      const near = slots.map((s) => slotTime.format(new Date(s))).join(', ')
      return near ? `Это время уже недоступно. Ближайшие: ${near}.` : 'Это время уже недоступно.'
    }
    case 'orders_paused':
      return 'Кафе сейчас не принимает заказы — попробуйте чуть позже.'
    case 'delivery_unavailable':
      return 'Доставка сейчас недоступна — можно забрать самому.'
    case 'address_required':
      return 'Укажите дом и квартиру.'
    case 'claim_requires_on_site':
      return 'Со скидкой «с проверкой» оплата только на месте.'
    case 'promotion_unavailable':
      return 'Эта скидка сейчас не действует.'
    case 'bad_change':
      return 'Сдача должна быть не меньше суммы заказа.'
    case 'location_closed':
      return 'Кафе сейчас закрыто — заказ можно оформить, когда откроемся.'
    case 'contact_required':
      return 'Укажите телефон и дайте согласие на обработку данных.'
    case 'empty_cart':
      return 'Корзина пуста.'
    case 'cart_has_unavailable':
      return 'Некоторых блюд уже нет — уберите их из корзины.'
    default:
      return 'Не получилось оформить заказ. Проверьте интернет и попробуйте ещё раз.'
  }
}
