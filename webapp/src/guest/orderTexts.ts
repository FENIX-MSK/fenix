import type { Order } from '../api/types'

// Guest-facing wording of the order lifecycle (EXPERIENCE.md › Voice and Tone).
export const STATUS_LABELS: Record<string, string> = {
  pending_payment: 'Ждём оплату',
  scheduled: 'Запланирован',
  new: 'Отправлен в кафе',
  accepted: 'Принят',
  cooking: 'Готовится',
  ready: 'Готов — можно забирать',
  handed_over: 'Выдан',
  delivering: 'В пути',
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

export function paymentText(order: Order): string {
  if (order.payment_status === 'paid') return `${PAYMENT_LABELS[order.payment_method]} · оплачен`
  if (order.payment_status === 'refunded') return `${PAYMENT_LABELS[order.payment_method]} · деньги возвращены`
  return PAYMENT_LABELS[order.payment_method] ?? order.payment_method
}

/** Why the order was not created, by the server's error code. */
export function orderErrorText(code: string | undefined): string {
  switch (code) {
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
