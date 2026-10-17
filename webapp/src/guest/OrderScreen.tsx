import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import { useSignals } from '../api/signals'
import type { Order } from '../api/types'
import { platform } from '../platform'
import { formatPrice } from './format'
import { addressText, FULFILMENT_LABELS, paymentText, scheduledText, STATUS_LABELS } from './orderTexts'
import { NETWORK_ERROR, RETRY } from './texts'

interface Props {
  orderId: string
  /** What the server returned on creation: shown at once, without a round trip. */
  initial?: Order
  onBack: () => void
}

// Fallback for a silent socket (a proxy that drops it without closing).
const POLL_MS = 30_000

const time = new Intl.DateTimeFormat('ru-RU', { hour: 'numeric', minute: '2-digit' })

type Loaded = { kind: 'loading' } | { kind: 'error' } | { kind: 'ready'; order: Order }

export function OrderScreen({ orderId, initial, onBack }: Props) {
  const [state, setState] = useState<Loaded>(initial ? { kind: 'ready', order: initial } : { kind: 'loading' })

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/v1/orders/{order_id}', { params: { path: { order_id: orderId } } })
      // Keep what is on screen if a refresh fails; only the first load shows an error.
      if (data) setState({ kind: 'ready', order: data })
      else setState((s) => (s.kind === 'ready' ? s : { kind: 'error' }))
    } catch {
      setState((s) => (s.kind === 'ready' ? s : { kind: 'error' }))
    }
  }, [orderId])

  useEffect(() => {
    const first = setTimeout(() => void refresh(), 0)
    const timer = setInterval(() => void refresh(), POLL_MS)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [refresh])
  useSignals(`order:${orderId}`, () => void refresh())
  useEffect(() => platform.showBackButton(onBack), [onBack])

  return (
    <main className="screen order">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button" onClick={onBack}>
          ← В меню
        </button>
      )}
      {state.kind === 'loading' && <div className="skeleton" style={{ height: 260, marginTop: 16 }} />}
      {state.kind === 'error' && (
        <div className="notice">
          <p>{NETWORK_ERROR}</p>
          <button type="button" className="secondary-button" onClick={() => void refresh()}>
            {RETRY}
          </button>
        </div>
      )}
      {state.kind === 'ready' && (
        <>
          <OrderDetails order={state.order} />
          {state.order.status === 'pending_payment' && (
            <TestPayment order={state.order} onChange={(order) => setState({ kind: 'ready', order })} />
          )}
        </>
      )}
    </main>
  )
}

function minutesLeft(until: string | null | undefined, now: number): number | null {
  if (!until) return null
  return Math.max(0, Math.ceil((new Date(until).getTime() - now) / 60_000))
}

/** The test provider's payment page, inside the Mini App (AD-9, story 3.5). */
function TestPayment({ order, onChange }: { order: Order; onChange: (order: Order) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15_000)
    return () => clearInterval(timer)
  }, [])

  const run = async (call: () => Promise<{ data?: Order }>) => {
    setBusy(true)
    setError(null)
    try {
      const { data } = await call()
      if (data) {
        onChange(data)
        platform.haptic(data.payment_status === 'paid' ? 'success' : 'error')
      } else setError('Не получилось — попробуйте ещё раз.')
    } catch {
      setError(NETWORK_ERROR)
    }
    setBusy(false)
  }
  const answer = (succeeded: boolean) =>
    run(() =>
      api.POST('/api/v1/payments/{payment_id}/test-result', {
        params: { path: { payment_id: order.payment_id! } },
        body: { succeeded },
      }),
    )
  const retry = () =>
    run(() => api.POST('/api/v1/orders/{order_id}/payments', { params: { path: { order_id: order.id } } }))

  const left = minutesLeft(order.pay_until, now)
  return (
    <section className="card payment">
      <h2 className="section">Оплата</h2>
      {order.payment_status === 'paid' && <p>Оплата прошла, передаём заказ в кафе…</p>}
      {order.payment_status === 'pending' && order.payment_id && (
        <>
          <p className="muted">Тестовый режим: деньги не списываются.</p>
          <div className="button-row">
            <button type="button" className="primary-button" disabled={busy} onClick={() => answer(true)}>
              Оплатить · {formatPrice(order.total)}
            </button>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => answer(false)}>
              Отказ банка (тест)
            </button>
          </div>
        </>
      )}
      {order.payment_status === 'failed' && (
        <>
          <p>Оплата не прошла.</p>
          <button type="button" className="primary-button" disabled={busy} onClick={retry}>
            Повторить
          </button>
        </>
      )}
      {left !== null && order.payment_status !== 'paid' && (
        <p className="caption muted">
          {left > 0 ? `Осталось ${left} мин — потом заказ отменится.` : 'Время на оплату вышло, заказ отменяется.'}
        </p>
      )}
      {error && <p className="error-text">{error}</p>}
    </section>
  )
}

export function OrderDetails({ order }: { order: Order }) {
  const cancelled = order.status === 'cancelled'
  const showReady = order.ready_at && ['accepted', 'cooking'].includes(order.status)
  return (
    <>
      <h1 className="title order-number">Заказ {order.number}</h1>
      <p className={cancelled ? 'order-status cancelled' : 'order-status'} role="status" aria-live="polite">
        {STATUS_LABELS[order.status] ?? order.status}
        {showReady && <span className="muted"> · готов к {time.format(new Date(order.ready_at!))}</span>}
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
        <p>
          {FULFILMENT_LABELS[order.fulfilment] ?? order.fulfilment}
          {scheduledText(order) && ` · ${scheduledText(order)}`}
        </p>
        {addressText(order) && <p>{addressText(order)}</p>}
        {order.delivery_fee > 0 && <p className="muted">Доставка {formatPrice(order.delivery_fee)}</p>}
        {order.change_from && <p className="muted">Сдача с {formatPrice(order.change_from)}</p>}
        <p>{paymentText(order)}</p>
        {order.discount_title && (
          <p className="muted">
            {order.discount_title}:{' '}
            {order.discount_status === 'confirmed'
              ? 'подтверждена'
              : order.discount_status === 'rejected'
                ? 'не подтверждена'
                : 'подтвердим при выдаче'}
          </p>
        )}
        {order.comment && <p className="muted">«{order.comment}»</p>}
      </section>
    </>
  )
}
