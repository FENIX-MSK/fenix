import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import { useSignals } from '../api/signals'
import type { Order } from '../api/types'
import { STATUS_LABELS } from './orderTexts'

/** The order in progress, over the menu until it is handed over (EXPERIENCE.md › IA). */
export function ActiveOrderBanner({ onOpen }: { onOpen: (order: Order) => void }) {
  const [order, setOrder] = useState<Order | null>(null)
  const load = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/v1/orders/active')
      setOrder(data ?? null)
    } catch {
      // The banner is a convenience; the menu works without it.
    }
  }, [])
  useEffect(() => {
    const first = setTimeout(() => void load(), 0)
    return () => clearTimeout(first)
  }, [load])
  useSignals(order ? `order:${order.id}` : null, () => void load())

  if (!order) return null
  return (
    <button type="button" className="active-order" onClick={() => onOpen(order)}>
      <span>
        Заказ <b>{order.number}</b> · {STATUS_LABELS[order.status] ?? order.status}
      </span>
      <span aria-hidden="true">›</span>
    </button>
  )
}
