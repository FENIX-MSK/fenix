import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../../api/client'
import { formatPrice } from '../../guest/format'
import { useSignals } from '../../api/signals'
import type { Board as BoardData, StaffOrder } from '../../api/types'
import { platform } from '../../platform'
import { OrderCard } from './OrderCard'
import { type Act, OrderSheet } from './OrderSheet'
import { Sheet } from './Sheet'
import { chime, enableSound, soundEnabled } from './sound'
import { clock, type Column, COLUMNS, LOAD_LABELS, nextStep } from './texts'

const HIGHLIGHT_MS = 5_000
// The chime repeats while a new order is neither opened nor accepted [ASSUMPTION].
const REMIND_MS = 30_000
// Fallback for a silent socket.
const POLL_MS = 30_000

interface Props {
  /** From the staff chat's «Открыть заказ»: open this card once the board loads. */
  openOrderId?: string | null
}

type Dialog =
  | { kind: 'accept'; order: StaffOrder }
  | { kind: 'pay'; order: StaffOrder; action: string }
  | { kind: 'kitchen' }
  | { kind: 'discount'; order: StaffOrder }
  | null

export function Board({ openOrderId }: Props) {
  const [board, setBoard] = useState<BoardData | null>(null)
  const [failed, setFailed] = useState(false)
  const [tab, setTab] = useState<Column>('new')
  const [selected, setSelected] = useState<string | null>(openOrderId ?? null)
  const [dialog, setDialog] = useState<Dialog>(null)
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [sound, setSound] = useState(soundEnabled())
  const known = useRef<Set<string> | null>(null)
  const seen = useRef<Set<string>>(new Set(openOrderId ? [openOrderId] : []))

  const load = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/v1/staff/orders')
      if (!data) throw new Error('board')
      setFailed(false)
      setBoard(data)
      const ids = new Set(data.orders.map((o) => o.id))
      if (known.current) {
        const fresh = data.orders.filter((o) => !known.current!.has(o.id)).map((o) => o.id)
        if (fresh.length) {
          chime()
          platform.haptic('success')
          setHighlighted((current) => new Set([...current, ...fresh]))
          setTimeout(
            () => setHighlighted((current) => new Set([...current].filter((id) => !fresh.includes(id)))),
            HIGHLIGHT_MS,
          )
        }
      }
      known.current = ids
    } catch {
      setFailed(true)
    }
  }, [])

  useEffect(() => {
    const first = setTimeout(() => void load(), 0)
    const poll = setInterval(() => void load(), POLL_MS)
    return () => {
      clearTimeout(first)
      clearInterval(poll)
    }
  }, [load])
  useSignals('staff', () => void load())

  const orders = useMemo(() => board?.orders ?? [], [board])
  useEffect(() => {
    const timer = setInterval(() => {
      if (orders.some((o) => o.status === 'new' && !seen.current.has(o.id))) chime()
    }, REMIND_MS)
    return () => clearInterval(timer)
  }, [orders])

  const replace = (order: StaffOrder) =>
    setBoard((current) =>
      current && {
        ...current,
        orders: current.orders.some((o) => o.id === order.id)
          ? current.orders.map((o) => (o.id === order.id ? order : o))
          : current.orders,
      },
    )

  const act: Act = async (order, action, extra = {}) => {
    setBusy(order.id)
    setNotice(null)
    seen.current.add(order.id)
    try {
      const { data, error } = await api.POST('/api/v1/staff/orders/{order_id}/actions', {
        params: { path: { order_id: order.id } },
        body: { action: action as never, expected_version: order.version, ...extra },
      })
      if (data) {
        platform.haptic('success')
        replace(data)
        void load()
        return true
      }
      platform.haptic('error')
      if (error?.error.code === 'order_conflict') setNotice(`Заказ ${order.number} уже изменили — показываем актуальный.`)
      else if (error?.error.code === 'transition_not_allowed') setNotice('Это действие сейчас недоступно.')
      else setNotice('Не получилось, попробуйте ещё раз.')
      void load()
    } catch {
      setNotice('Не получилось связаться с сервером.')
    } finally {
      setBusy(null)
    }
    return false
  }

  const markPaid = async (order: StaffOrder, method: 'cash' | 'card') => {
    try {
      const { data } = await api.POST('/api/v1/staff/orders/{order_id}/payment', {
        params: { path: { order_id: order.id } },
        body: { method },
      })
      if (data) {
        replace(data)
        return true
      }
    } catch {
      // below
    }
    setNotice('Не получилось отметить оплату.')
    return false
  }

  const decideDiscount = async (order: StaffOrder, confirm: boolean) => {
    try {
      const { data, error } = await api.POST('/api/v1/staff/orders/{order_id}/discount', {
        params: { path: { order_id: order.id } },
        body: { confirm, expected_version: order.version },
      })
      if (data) {
        replace(data)
        return true
      }
      setNotice(error?.error.code === 'order_conflict' ? 'Заказ уже изменили.' : 'Не получилось.')
      void load()
    } catch {
      setNotice('Не получилось связаться с сервером.')
    }
    return false
  }

  const next = (order: StaffOrder) => {
    seen.current.add(order.id)
    if (order.status === 'new') return setDialog({ kind: 'accept', order })
    const step = nextStep(order)
    if (!step) return
    // The claimed discount is decided before the order leaves (FR-23).
    if (['hand_over', 'deliver'].includes(step.action) && order.discount_status === 'pending') {
      return setDialog({ kind: 'discount', order })
    }
    if (['hand_over', 'deliver'].includes(step.action) && order.payment_status !== 'paid') {
      return setDialog({ kind: 'pay', order, action: step.action })
    }
    void act(order, step.action)
  }

  const open = (id: string) => {
    seen.current.add(id)
    setSelected(id)
  }

  const selectedOrder = orders.find((o) => o.id === selected)
  const counts = Object.fromEntries(
    COLUMNS.map((c) => [c.id, orders.filter((o) => c.statuses.includes(o.status)).length]),
  ) as Record<Column, number>

  return (
    <div className="board">
      <div className="board-head">
        <h1 className="title staff-title">Заказы</h1>
        {board && (
          <button type="button" className={`kitchen-chip ${board.kitchen.level}`} onClick={() => setDialog({ kind: 'kitchen' })}>
            Кухня: {LOAD_LABELS[board.kitchen.level]} · {board.kitchen.in_work} в работе
            {board.kitchen.manual && ' · вручную'}
          </button>
        )}
      </div>
      {!sound && (
        <button
          type="button"
          className="secondary-button board-sound"
          onClick={async () => setSound(await enableSound())}
        >
          🔔 Включить звук новых заказов
        </button>
      )}
      {notice && (
        <p className="error-text" role="alert">
          {notice}
        </p>
      )}
      {failed && !board && <p className="error-text">Не получилось загрузить заказы.</p>}
      {!board && !failed && <div className="skeleton" style={{ height: 240, marginTop: 16 }} />}
      {board && (
        <>
          <div className="board-tabs" role="tablist">
            {COLUMNS.map((column) => (
              <button
                key={column.id}
                type="button"
                role="tab"
                aria-selected={tab === column.id}
                className={tab === column.id ? 'board-tab active' : 'board-tab'}
                onClick={() => setTab(column.id)}
              >
                {column.label} {counts[column.id] > 0 && <span className="board-count">{counts[column.id]}</span>}
              </button>
            ))}
          </div>
          {orders.length === 0 && <p className="muted board-empty">Новых заказов нет</p>}
          <div className="board-columns">
            {COLUMNS.map((column) => {
              // Newest on top: a new card appears at the top of its column.
              const items = orders.filter((o) => column.statuses.includes(o.status)).reverse()
              return (
                <section
                  key={column.id}
                  className={tab === column.id ? 'board-column active' : 'board-column'}
                  aria-label={column.label}
                >
                  <h2 className="board-column-title">
                    {column.label} <span className="muted">{items.length}</span>
                  </h2>
                  {items.map((order) => (
                    <OrderCard
                      key={order.id}
                      order={order}
                      highlighted={highlighted.has(order.id)}
                      busy={busy === order.id}
                      onOpen={() => open(order.id)}
                      onNext={() => next(order)}
                    />
                  ))}
                </section>
              )
            })}
          </div>
        </>
      )}
      {selectedOrder && (
        <OrderSheet
          order={selectedOrder}
          onClose={() => setSelected(null)}
          onAct={act}
          onMarkPaid={markPaid}
          onDiscount={decideDiscount}
        />
      )}
      {selected && board && !selectedOrder && (
        <ClosedOrder orderId={selected} onClose={() => setSelected(null)} />
      )}
      {dialog?.kind === 'accept' && board && (
        <AcceptSheet
          order={dialog.order}
          prepMinutes={board.prep_minutes}
          onClose={() => setDialog(null)}
          onAccept={async (readyAt) => {
            if (await act(dialog.order, 'accept', { ready_at: readyAt.toISOString() })) setDialog(null)
          }}
        />
      )}
      {dialog?.kind === 'kitchen' && board && (
        <KitchenSheet
          manual={board.kitchen.manual}
          manualUntil={board.kitchen.manual_until ?? null}
          onClose={() => setDialog(null)}
          onSet={async (level, minutes) => {
            try {
              await api.POST('/api/v1/staff/orders/kitchen', { body: { level, minutes } })
              setDialog(null)
              void load()
            } catch {
              setNotice('Не получилось изменить загруженность.')
            }
          }}
        />
      )}
      {dialog?.kind === 'discount' && (
        <Sheet title={`Скидка ${dialog.order.number}`} onClose={() => setDialog(null)}>
          <p>🎂 {dialog.order.discount_title}. Проверьте документ.</p>
          <div className="button-row sheet-section">
            <button
              type="button"
              className="primary-button"
              onClick={async () => {
                if (await decideDiscount(dialog.order, true)) setDialog(null)
              }}
            >
              Подтвердить скидку
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={async () => {
                if (await decideDiscount(dialog.order, false)) setDialog(null)
              }}
            >
              Снять — без скидки {formatPrice(dialog.order.total_without_claim ?? dialog.order.total)}
            </button>
          </div>
        </Sheet>
      )}
      {dialog?.kind === 'pay' && (
        <Sheet title={`Выдать ${dialog.order.number}`} onClose={() => setDialog(null)}>
          <p>Заказ не оплачен. Как гость заплатил?</p>
          <div className="button-row sheet-section">
            {(['cash', 'card'] as const).map((method) => (
              <button
                key={method}
                type="button"
                className="primary-button"
                onClick={async () => {
                  if (await act(dialog.order, dialog.action, { paid_with: method })) setDialog(null)
                }}
              >
                {method === 'cash' ? 'Наличными' : 'Картой'}
              </button>
            ))}
          </div>
        </Sheet>
      )}
    </div>
  )
}

const PRESETS = [10, 20, 30, 45, 60]

function AcceptSheet({
  order,
  prepMinutes,
  onClose,
  onAccept,
}: {
  order: StaffOrder
  prepMinutes: number
  onClose: () => void
  onAccept: (readyAt: Date) => void
}) {
  const [minutes, setMinutes] = useState(prepMinutes)
  const [now] = useState(() => Date.now())
  const readyAt = new Date(now + minutes * 60_000)
  const options = [...new Set([prepMinutes, ...PRESETS])].sort((a, b) => a - b)
  return (
    <Sheet title={`Принять ${order.number}`} onClose={onClose}>
      <p>Когда будет готов?</p>
      <div className="chips sheet-section">
        {options.map((value) => (
          <button
            key={value}
            type="button"
            className={value === minutes ? 'chip active' : 'chip'}
            aria-pressed={value === minutes}
            onClick={() => setMinutes(value)}
          >
            {value} мин
          </button>
        ))}
      </div>
      <button type="button" className="primary-button wide" onClick={() => onAccept(readyAt)}>
        Принять · к {clock.format(readyAt)}
      </button>
    </Sheet>
  )
}

/** A card opened from the chat after it left the board (handed over or cancelled). */
function ClosedOrder({ orderId, onClose }: { orderId: string; onClose: () => void }) {
  const [order, setOrder] = useState<StaffOrder | null | undefined>(undefined)
  useEffect(() => {
    api
      .GET('/api/v1/staff/orders/{order_id}', { params: { path: { order_id: orderId } } })
      .then(({ data }) => setOrder(data ?? null))
      .catch(() => setOrder(null))
  }, [orderId])
  if (order === undefined) return null
  if (order === null) {
    return (
      <Sheet title="Заказ" onClose={onClose}>
        <p>Заказ не найден.</p>
      </Sheet>
    )
  }
  return <OrderSheet order={order} onClose={onClose} onAct={async () => false} onMarkPaid={async () => false} />
}

type Level = 'calm' | 'moderate' | 'busy'

function KitchenSheet({
  manual,
  manualUntil,
  onClose,
  onSet,
}: {
  manual: boolean
  manualUntil: string | null
  onClose: () => void
  onSet: (level: Level | null, minutes: 30 | 60 | null) => void
}) {
  const [level, setLevel] = useState<Level>('busy')
  const [minutes, setMinutes] = useState<30 | 60 | null>(30)
  return (
    <Sheet title="Загруженность кухни" onClose={onClose}>
      {manual && (
        <p className="muted">
          Сейчас задано вручную{manualUntil ? ` · до ${clock.format(new Date(manualUntil))}` : ' · до отмены'}
        </p>
      )}
      <div className="chips sheet-section">
        {(['calm', 'moderate', 'busy'] as const).map((value) => (
          <button
            key={value}
            type="button"
            className={level === value ? 'chip active' : 'chip'}
            aria-pressed={level === value}
            onClick={() => setLevel(value)}
          >
            {{ calm: 'Спокойно', moderate: 'Умеренно', busy: 'Загружены' }[value]}
          </button>
        ))}
      </div>
      <div className="chips sheet-section">
        {([30, 60, null] as const).map((value) => (
          <button
            key={String(value)}
            type="button"
            className={minutes === value ? 'chip active' : 'chip'}
            aria-pressed={minutes === value}
            onClick={() => setMinutes(value)}
          >
            {value ? `${value} мин` : 'До отмены'}
          </button>
        ))}
      </div>
      <button type="button" className="primary-button wide" onClick={() => onSet(level, minutes)}>
        Применить
      </button>
      {manual && (
        <button type="button" className="secondary-button wide-secondary" onClick={() => onSet(null, null)}>
          Вернуть авто
        </button>
      )}
    </Sheet>
  )
}
