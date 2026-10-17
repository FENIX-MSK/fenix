import { useState } from 'react'

import type { StaffOrder } from '../../api/types'
import { formatPrice } from '../../guest/format'
import { Sheet } from './Sheet'
import { ACTION_LABELS, CANCEL_REASONS, clock, paymentBadge, STATUS_LABELS } from './texts'

export type Act = (order: StaffOrder, action: string, extra?: Record<string, unknown>) => Promise<boolean>

interface Props {
  order: StaffOrder
  onClose: () => void
  onAct: Act
  onMarkPaid: (order: StaffOrder, method: 'cash' | 'card') => Promise<boolean>
}

const CANCELLABLE = new Set(['new', 'accepted', 'cooking', 'ready', 'scheduled'])

/** Everything about one order, with the secondary actions behind it (FR-22, FR-25). */
export function OrderSheet({ order, onClose, onAct, onMarkPaid }: Props) {
  const [cancelling, setCancelling] = useState(false)
  const badge = paymentBadge(order)
  const onSite = order.payment_method !== 'online'
  const canMarkPaid = onSite && order.payment_status !== 'paid' && order.status !== 'cancelled'
  return (
    <Sheet title={`Заказ ${order.number} · ${STATUS_LABELS[order.status] ?? order.status}`} onClose={onClose}>
      <section className="sheet-section">
        <p>
          {order.customer_name} ·{' '}
          <a href={`tel:${order.customer_phone}`}>{order.customer_phone}</a>
          {!order.phone_verified && <span className="muted"> (введён вручную)</span>}
        </p>
        <p className="muted">
          Самовывоз · оформлен в {clock.format(new Date(order.created_at))}
          {order.ready_at && ` · готов к ${clock.format(new Date(order.ready_at))}`}
        </p>
      </section>
      <ul className="order-lines sheet-section">
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
      {order.comment && <p className="board-comment">💬 {order.comment}</p>}
      <p>
        <span className={badge.paid ? 'badge paid' : 'badge'}>{badge.text}</span>
      </p>
      {order.cancel_reason && <p className="error-text">Причина отмены: {order.cancel_reason}</p>}

      {canMarkPaid && (
        <div className="button-row sheet-section">
          <button type="button" className="secondary-button" onClick={() => onMarkPaid(order, 'cash')}>
            Оплачено наличными
          </button>
          <button type="button" className="secondary-button" onClick={() => onMarkPaid(order, 'card')}>
            Оплачено картой
          </button>
        </div>
      )}

      {CANCELLABLE.has(order.status) &&
        (cancelling ? (
          <CancelForm order={order} onAct={onAct} onDone={onClose} onBack={() => setCancelling(false)} />
        ) : (
          <button type="button" className="secondary-button danger sheet-section" onClick={() => setCancelling(true)}>
            Отменить заказ
          </button>
        ))}

      <h3 className="section sheet-section">Журнал</h3>
      <ol className="order-log">
        {(order.log ?? []).map((entry, index) => (
          <li key={index}>
            <span className="muted">{clock.format(new Date(entry.at))}</span>{' '}
            {ACTION_LABELS[entry.action] ?? entry.action}
            {entry.actor_name ? ` · ${entry.actor_name}` : entry.actor_kind === 'system' ? ' · система' : ''}
            {entry.note && <span className="muted"> — {entry.note}</span>}
          </li>
        ))}
      </ol>
    </Sheet>
  )
}

function CancelForm({
  order,
  onAct,
  onDone,
  onBack,
}: {
  order: StaffOrder
  onAct: Act
  onDone: () => void
  onBack: () => void
}) {
  const [reason, setReason] = useState<string | null>(null)
  const [other, setOther] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const note = reason === 'other' ? other.trim() : reason
  const submit = async () => {
    if (!note) return
    // Irreversible: the second tap confirms (EXPERIENCE.md › Confirmations).
    if (!confirm) return setConfirm(true)
    setBusy(true)
    const ok = await onAct(order, 'cancel', { note })
    setBusy(false)
    if (ok) onDone()
  }
  return (
    <div className="cancel-form sheet-section">
      <p>Почему отменяем? Гость причину не увидит.</p>
      {[...CANCEL_REASONS, 'other'].map((item) => (
        <label key={item} className="option">
          <input
            type="radio"
            name="cancel-reason"
            checked={reason === item}
            onChange={() => {
              setReason(item)
              setConfirm(false)
            }}
          />
          <span className="option-name">{item === 'other' ? 'Другое' : item}</span>
        </label>
      ))}
      {reason === 'other' && (
        <input
          className="search"
          value={other}
          maxLength={500}
          placeholder="Причина"
          onChange={(event) => setOther(event.target.value)}
        />
      )}
      <div className="button-row">
        <button type="button" className="secondary-button" onClick={onBack}>
          Не отменять
        </button>
        <button type="button" className="primary-button danger-fill" disabled={!note || busy} onClick={submit}>
          {confirm ? 'Точно отменить' : 'Отменить заказ'}
        </button>
      </div>
    </div>
  )
}
