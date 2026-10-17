import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Order } from '../api/types'
import { platform } from '../platform'
import { useCart } from './cart'
import { formatPrice } from './format'
import { STATUS_LABELS } from './orderTexts'
import { SunMark } from './SunMark'
import { NETWORK_ERROR, RETRY } from './texts'

interface Props {
  onBack: () => void
  onOpen: (order: Order) => void
  /** After «Повторить»: to the cart, with the names of what could not be added. */
  onRepeated: (skipped: string[]) => void
}

const date = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', hour: 'numeric', minute: '2-digit' })

/** «Мои заказы» (FR-17, FR-18). */
export function HistoryScreen({ onBack, onOpen, onRepeated }: Props) {
  const [orders, setOrders] = useState<Order[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [repeating, setRepeating] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { set: setCart } = useCart()
  useEffect(() => platform.showBackButton(onBack), [onBack])

  const load = useCallback(async (after: string | null) => {
    setState('loading')
    try {
      const { data } = await api.GET('/api/v1/orders', { params: { query: after ? { cursor: after } : {} } })
      if (!data) throw new Error('orders')
      setOrders((current) => (after ? [...current, ...data.orders] : data.orders))
      setCursor(data.next_cursor ?? null)
      setState('ready')
    } catch {
      setState('error')
    }
  }, [])

  useEffect(() => {
    const first = setTimeout(() => void load(null), 0)
    return () => clearTimeout(first)
  }, [load])

  const repeat = async (order: Order) => {
    setRepeating(order.id)
    setError(null)
    try {
      const { data } = await api.POST('/api/v1/orders/{order_id}/repeat', { params: { path: { order_id: order.id } } })
      if (data) {
        setCart(data.cart)
        platform.haptic(data.added > 0 ? 'success' : 'error')
        if (data.added > 0) return onRepeated(data.skipped)
        setError('Ничего из этого заказа сейчас нет в меню.')
      } else setError('Не получилось повторить заказ.')
    } catch {
      setError(NETWORK_ERROR)
    } finally {
      setRepeating(null)
    }
  }

  return (
    <main className="screen history">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button" onClick={onBack}>
          ← В меню
        </button>
      )}
      <h1 className="title staff-title">Мои заказы</h1>
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
      {state === 'ready' && orders.length === 0 && (
        <div className="empty">
          <SunMark size={40} />
          <p className="muted">Здесь появятся ваши заказы</p>
          <button type="button" className="secondary-button" onClick={onBack}>
            В меню
          </button>
        </div>
      )}
      <ul className="history-list">
        {orders.map((order) => (
          <li key={order.id} className="card history-card">
            <button type="button" className="history-open" onClick={() => onOpen(order)}>
              <span className="history-head">
                <b>{order.number}</b>
                <span className="muted">{date.format(new Date(order.created_at))}</span>
              </span>
              <span className="history-lines">
                {order.lines.map((line) => (line.quantity > 1 ? `${line.title} × ${line.quantity}` : line.title)).join(', ')}
              </span>
              <span className="history-head">
                <span className={order.status === 'cancelled' ? 'error-text' : 'muted'}>
                  {STATUS_LABELS[order.status] ?? order.status}
                </span>
                <span>{formatPrice(order.total)}</span>
              </span>
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={repeating !== null}
              onClick={() => void repeat(order)}
            >
              {repeating === order.id ? 'Добавляем…' : 'Повторить'}
            </button>
          </li>
        ))}
      </ul>
      {state === 'loading' && <div className="skeleton" style={{ height: 120, marginTop: 16 }} />}
      {state === 'error' && (
        <div className="notice">
          <p>{NETWORK_ERROR}</p>
          <button type="button" className="secondary-button" onClick={() => void load(cursor)}>
            {RETRY}
          </button>
        </div>
      )}
      {state === 'ready' && cursor && (
        <button type="button" className="secondary-button history-more" onClick={() => void load(cursor)}>
          Показать ещё
        </button>
      )}
    </main>
  )
}
