import { useCallback, useEffect } from 'react'

import { api } from '../api/client'
import type { Order } from '../api/types'
import { platform } from '../platform'
import { formatPrice } from './format'
import { FULFILMENT_LABELS, paymentText, STATUS_LABELS } from './orderTexts'
import { NETWORK_ERROR, RETRY } from './texts'
import { useRemote } from './useRemote'

interface Props {
  orderId: string
  /** What the server returned on creation: shown at once, without a round trip. */
  initial?: Order
  onBack: () => void
}

const time = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })

export function OrderScreen({ orderId, initial, onBack }: Props) {
  const load = useCallback(
    () => api.GET('/api/v1/orders/{order_id}', { params: { path: { order_id: orderId } } }),
    [orderId],
  )
  const { state, reload } = useRemote(load)
  useEffect(() => platform.showBackButton(onBack), [onBack])
  const order = state.kind === 'ready' ? state.data : initial

  return (
    <main className="screen order">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button" onClick={onBack}>
          ← В меню
        </button>
      )}
      {!order && state.kind === 'loading' && <div className="skeleton" style={{ height: 260, marginTop: 16 }} />}
      {!order && state.kind === 'error' && (
        <div className="notice">
          <p>{NETWORK_ERROR}</p>
          <button type="button" className="secondary-button" onClick={reload}>
            {RETRY}
          </button>
        </div>
      )}
      {order && <OrderDetails order={order} />}
    </main>
  )
}

export function OrderDetails({ order }: { order: Order }) {
  const cancelled = order.status === 'cancelled'
  return (
    <>
      <h1 className="title staff-title">Заказ {order.number}</h1>
      <p className={cancelled ? 'order-status cancelled' : 'order-status'} role="status">
        {STATUS_LABELS[order.status] ?? order.status}
        {order.ready_at && !cancelled && order.status !== 'handed_over' && (
          <span className="muted"> · к {time.format(new Date(order.ready_at))}</span>
        )}
      </p>
      <section className="card">
        <h2 className="section">Состав</h2>
        <ul className="order-lines">
          {order.lines.map((line, index) => (
            <li key={index} className="order-line">
              <div>
                <span>{line.title}</span>
                {line.quantity > 1 && <span className="muted"> × {line.quantity}</span>}
                {line.modifier_names.length > 0 && <p className="caption muted">{line.modifier_names.join(', ')}</p>}
              </div>
              <span className="price">{formatPrice(line.total_price)}</span>
            </li>
          ))}
        </ul>
        <p className="order-total">
          <span>Итого</span>
          <span className="price">{formatPrice(order.total)}</span>
        </p>
      </section>
      <section className="card">
        <p>{FULFILMENT_LABELS[order.fulfilment] ?? order.fulfilment}</p>
        <p>{paymentText(order)}</p>
        {order.comment && <p className="muted">«{order.comment}»</p>}
      </section>
    </>
  )
}
