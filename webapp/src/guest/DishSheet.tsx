import { type PointerEvent as ReactPointerEvent, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import { useCart } from './cart'
import { MainAction } from './MainAction'
import type { DishDetail, MenuDish, ModifierGroup } from '../api/types'
import { platform } from '../platform'
import { formatPrice } from './format'
import { SunMark } from './SunMark'
import { NETWORK_ERROR, RETRY } from './texts'
import { type PriceState, useDishPrice } from './useDishPrice'

interface Props {
  dish: MenuDish
  onClose: () => void
}

type Loaded = { kind: 'loading' } | { kind: 'ready'; dish: DishDetail } | { kind: 'error' }

const MAX_QUANTITY = 99
const SWIPE_CLOSE_PX = 80

export function DishSheet({ dish, onClose }: Props) {
  const [loaded, setLoaded] = useState<Loaded>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    api
      .GET('/api/v1/menu/dishes/{dish_id}', { params: { path: { dish_id: dish.id } } })
      .then(({ data }) => {
        if (!cancelled) setLoaded(data ? { kind: 'ready', dish: data } : { kind: 'error' })
      })
      .catch(() => {
        if (!cancelled) setLoaded({ kind: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [dish.id, attempt])

  useEffect(() => platform.showBackButton(onClose), [onClose])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    // The menu keeps its scroll position underneath; only the sheet scrolls while open.
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = overflow
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const drag = useSwipeDown(onClose)
  const sheetRef = useRef<HTMLDivElement>(null)
  // Move focus into the dialog so screen readers and keyboards start inside it.
  useEffect(() => sheetRef.current?.focus(), [])

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div
        className="sheet"
        ref={sheetRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dish-sheet-title"
        onClick={(event) => event.stopPropagation()}
        style={drag.offset ? { transform: `translateY(${drag.offset}px)` } : undefined}
      >
        <div className="sheet-grip" {...drag.handlers}>
          <span className="sheet-grip-bar" aria-hidden="true" />
          {!platform.hasNativeBackButton && (
            <button type="button" className="icon-button sheet-close" onClick={onClose} aria-label="Закрыть">
              ✕
            </button>
          )}
        </div>
        <div className="sheet-photo" aria-hidden="true">
          {dish.photo_url ? <img src={dish.photo_url} alt="" /> : <SunMark size={64} />}
        </div>
        <h2 className="sheet-title" id="dish-sheet-title">
          {dish.name}
        </h2>
        {loaded.kind === 'loading' && <div className="skeleton" style={{ height: 160, marginTop: 16 }} />}
        {loaded.kind === 'error' && (
          <div className="notice">
            <p>{NETWORK_ERROR}</p>
            <button type="button" className="secondary-button" onClick={() => setAttempt((n) => n + 1)}>
              {RETRY}
            </button>
          </div>
        )}
        {loaded.kind === 'ready' && <DishChoice dish={loaded.dish} onAdded={onClose} />}
      </div>
    </div>
  )
}

function DishChoice({ dish, onAdded }: { dish: DishDetail; onAdded: () => void }) {
  const [sizeId, setSizeId] = useState<string | null>(() => dish.sizes.find((s) => s.available)?.id ?? null)
  const [chosen, setChosen] = useState<Record<string, string[]>>({})
  const [quantity, setQuantity] = useState(1)
  const [rejectedGroup, setRejectedGroup] = useState<string | null>(null)

  const modifierIds = dish.groups.flatMap((g) => chosen[g.id] ?? [])
  const price = useDishPrice({ dishId: dish.id, sizeId, modifierIds, quantity })
  const missing = new Set(price.kind === 'ready' ? price.price.missing_groups.map((g) => g.id) : [])
  const { set: setCart } = useCart()
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const addPrice = price.kind === 'ready' && price.price.complete ? price.price.total_price : null
  const canAdd = addPrice !== null && sizeId !== null

  const add = async () => {
    if (!canAdd || !sizeId) return
    setAdding(true)
    setAddError(null)
    try {
      const { data } = await api.POST('/api/v1/cart/items', {
        body: { dish_id: dish.id, size_id: sizeId, modifier_ids: modifierIds, quantity },
      })
      if (data) {
        setCart(data)
        platform.haptic('success')
        return onAdded()
      }
    } catch {
      // below
    }
    setAdding(false)
    setAddError('Не получилось добавить, попробуйте ещё раз.')
  }

  const toggle = (group: ModifierGroup, modifierId: string) => {
    const current = chosen[group.id] ?? []
    let next: string[]
    if (current.includes(modifierId)) {
      // A required single choice stays chosen; it can only be switched.
      if (group.max_choice === 1 && group.min_choice >= 1) return
      next = current.filter((id) => id !== modifierId)
    } else if (group.max_choice === 1) {
      next = [modifierId]
    } else if (current.length >= group.max_choice) {
      // Over the maximum: not applied (FR-4), with a short error vibration.
      platform.haptic('error')
      setRejectedGroup(group.id)
      window.setTimeout(() => setRejectedGroup(null), 400)
      return
    } else {
      next = [...current, modifierId]
    }
    platform.haptic('selection')
    setChosen({ ...chosen, [group.id]: next })
  }

  return (
    <>
      {dish.description && <p className="sheet-description muted">{dish.description}</p>}
      {dish.portion && <p className="caption muted">{dish.portion}</p>}

      {dish.sizes.length > 1 && (
        <fieldset className="choice-group">
          <legend className="choice-legend">Размер</legend>
          {dish.sizes.map((size) => (
            <label key={size.id} className={size.available ? 'option' : 'option disabled'}>
              <input
                type="radio"
                name="size"
                checked={sizeId === size.id}
                disabled={!size.available}
                onChange={() => {
                  platform.haptic('selection')
                  setSizeId(size.id)
                }}
              />
              <span className="option-name">{size.name}</span>
              <span className="option-price">{size.available ? formatPrice(size.price) : 'Закончилось'}</span>
            </label>
          ))}
        </fieldset>
      )}

      {dish.groups.map((group) => {
        const single = group.max_choice === 1
        const selected = chosen[group.id] ?? []
        const classes = ['choice-group']
        if (missing.has(group.id)) classes.push('needs-choice')
        if (rejectedGroup === group.id) classes.push('rejected')
        return (
          <fieldset key={group.id} className={classes.join(' ')}>
            <legend className="choice-legend">
              {group.name}
              <span className="caption muted">
                {group.min_choice >= 1 ? ' · обязательно' : single ? '' : ` · до ${group.max_choice}`}
              </span>
            </legend>
            {group.modifiers.map((modifier) => (
              <label key={modifier.id} className={modifier.available ? 'option' : 'option disabled'}>
                <input
                  type={single ? 'radio' : 'checkbox'}
                  name={group.id}
                  checked={selected.includes(modifier.id)}
                  disabled={!modifier.available}
                  onChange={() => toggle(group, modifier.id)}
                  onClick={() => single && selected.includes(modifier.id) && toggle(group, modifier.id)}
                />
                <span className="option-name">{modifier.name}</span>
                <span className="option-price">
                  {!modifier.available ? 'Закончилось' : modifier.price_delta ? `+${formatPrice(modifier.price_delta)}` : ''}
                </span>
              </label>
            ))}
          </fieldset>
        )
      })}

      <div className="sheet-footer">
        <div className="stepper" role="group" aria-label="Количество">
          <button
            type="button"
            className="icon-button"
            aria-label="Меньше"
            disabled={quantity <= 1}
            onClick={() => setQuantity(quantity - 1)}
          >
            −
          </button>
          <span className="stepper-value" aria-live="polite">
            {quantity}
          </span>
          <button
            type="button"
            className="icon-button"
            aria-label="Больше"
            disabled={quantity >= MAX_QUANTITY}
            onClick={() => setQuantity(quantity + 1)}
          >
            +
          </button>
        </div>
        <Total price={price} />
      </div>
      {addError && <p className="error-text">{addError}</p>}
      <MainAction
        text={addPrice !== null ? `Добавить · ${formatPrice(addPrice)}` : 'Добавить'}
        disabled={!canAdd}
        loading={adding}
        onClick={add}
      />
    </>
  )
}

function Total({ price }: { price: PriceState }) {
  let content: string
  if (price.kind === 'pending' || price.kind === 'idle') content = ''
  else if (price.kind === 'error') content = 'Не получилось посчитать'
  else if (price.kind === 'invalid') content = 'Этот вариант сейчас недоступен'
  else if (!price.price.complete) {
    const names = price.price.missing_groups.map((g) => accusative(g.name.toLowerCase()))
    content = `Выберите ${names.join(' и ')}`
  } else content = formatPrice(price.price.total_price)

  const busy = price.kind === 'pending'
  const isHint = price.kind === 'ready' && !price.price.complete
  return (
    <div className={isHint ? 'total hint' : 'total'} aria-live="polite" aria-busy={busy}>
      {busy ? <span className="spinner" role="status" aria-label="Считаем цену" /> : content}
    </div>
  )
}

/**
 * «Выберите котлету»: group names are nominative; feminine -а/-я take -у/-ю, the rest
 * (соус, размер, добавки) read the same. Enough for one-word group names.
 */
function accusative(word: string): string {
  if (word.endsWith('а')) return `${word.slice(0, -1)}у`
  if (word.endsWith('я')) return `${word.slice(0, -1)}ю`
  return word
}

/** Drag the sheet down by its grip; past the threshold it closes. */
function useSwipeDown(onClose: () => void) {
  const start = useRef<number | null>(null)
  const [offset, setOffset] = useState(0)
  return {
    offset,
    handlers: {
      onPointerDown(event: ReactPointerEvent) {
        start.current = event.clientY
        event.currentTarget.setPointerCapture(event.pointerId)
      },
      onPointerMove(event: ReactPointerEvent) {
        if (start.current !== null) setOffset(Math.max(0, event.clientY - start.current))
      },
      onPointerUp() {
        const shouldClose = offset > SWIPE_CLOSE_PX
        start.current = null
        setOffset(0)
        if (shouldClose) onClose()
      },
      onPointerCancel() {
        start.current = null
        setOffset(0)
      },
    },
  }
}
