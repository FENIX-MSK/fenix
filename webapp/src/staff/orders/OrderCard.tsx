import type { StaffOrder } from '../../api/types'
import { formatPrice } from '../../guest/format'
import { addressLine, clock, nextStep, paymentBadge } from './texts'

interface Props {
  order: StaffOrder
  highlighted: boolean
  busy: boolean
  onOpen: () => void
  onNext: () => void
}

/** A card on the board: what to make, and the one next step (EXPERIENCE.md). */
export function OrderCard({ order, highlighted, busy, onOpen, onNext }: Props) {
  const next = nextStep(order)
  const badge = paymentBadge(order)
  return (
    <article className={highlighted ? 'board-card highlighted' : 'board-card'}>
      <button type="button" className="board-card-body" onClick={onOpen} aria-label={`Заказ ${order.number}, подробнее`}>
        <div className="board-card-head">
          <span className="board-number">{order.number}</span>
          <span className="muted">{clock.format(new Date(order.created_at))}</span>
          {order.fulfilment === 'delivery' && <span className="badge">Доставка</span>}
          {order.ready_at && order.status !== 'new' && (
            <span className="board-ready">к {clock.format(new Date(order.ready_at))}</span>
          )}
        </div>
        <ul className="board-lines">
          {order.lines.map((line, index) => (
            <li key={index}>
              {line.quantity > 1 && <b>{line.quantity} × </b>}
              {line.title}
              {line.modifier_names.length > 0 && <span className="muted"> · {line.modifier_names.join(', ')}</span>}
            </li>
          ))}
        </ul>
        {order.discount_status === 'pending' && (
          <p className="board-claim">🎂 {order.discount_title} — проверить документ</p>
        )}
        {order.comment && <p className="board-comment">💬 {order.comment}</p>}
        {order.fulfilment === 'delivery' && (
          <p className="board-address">
            🏠 {addressLine(order)} · {order.customer_phone}
            {order.change_from ? ` · сдача с ${formatPrice(order.change_from)}` : ''}
          </p>
        )}
        <p className="board-meta">
          <span className={badge.paid ? 'badge paid' : 'badge'}>{badge.text}</span>
          <span>{formatPrice(order.total)}</span>
        </p>
      </button>
      {next && (
        <button type="button" className="primary-button board-next" disabled={busy} onClick={onNext}>
          {next.label}
        </button>
      )}
    </article>
  )
}
