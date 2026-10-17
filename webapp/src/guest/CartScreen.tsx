import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { CartLine } from '../api/types'
import { platform } from '../platform'
import { useCart } from './cart'
import { formatPrice } from './format'
import { MainAction } from './MainAction'
import { SunMark } from './SunMark'

interface Props {
  onBack: () => void
  onCheckout?: () => void
}

export function CartScreen({ onBack, onCheckout }: Props) {
  const { cart, set } = useCart()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => platform.showBackButton(onBack), [onBack])

  const change = async (line: CartLine, quantity: number) => {
    setError(null)
    try {
      const { data } = await api.PATCH('/api/v1/cart/items/{item_id}', {
        params: { path: { item_id: line.id } },
        body: { quantity },
      })
      if (data) return set(data)
    } catch {
      // below
    }
    setError('Не получилось изменить корзину, попробуйте ещё раз.')
  }

  const unavailable = cart?.lines.filter((l) => !l.available) ?? []
  return (
    <main className="screen cart">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button" onClick={onBack}>
          ← В меню
        </button>
      )}
      <h1 className="title staff-title">Корзина</h1>
      {!cart || cart.lines.length === 0 ? (
        <div className="empty">
          <SunMark size={40} />
          <p className="muted">В корзине пока ничего нет</p>
          <button type="button" className="secondary-button" onClick={onBack}>
            В меню
          </button>
        </div>
      ) : (
        <>
          <ul className="cart-lines">
            {cart.lines.map((line) => (
              <li key={line.id} className={line.available ? 'cart-line' : 'cart-line unavailable'}>
                <div className="cart-line-photo" aria-hidden="true">
                  {line.photo_url ? <img src={line.photo_url} alt="" /> : <SunMark size={28} />}
                </div>
                <div className="cart-line-body">
                  <div className="dish-name">{line.title}</div>
                  {line.modifier_names.length > 0 && <div className="caption muted">{line.modifier_names.join(', ')}</div>}
                  {line.available ? (
                    <div className="cart-line-footer">
                      <div className="stepper" role="group" aria-label={`Количество: ${line.title}`}>
                        <button type="button" className="icon-button" aria-label="Меньше" onClick={() => change(line, line.quantity - 1)}>
                          −
                        </button>
                        <span className="stepper-value">{line.quantity}</span>
                        <button
                          type="button"
                          className="icon-button"
                          aria-label="Больше"
                          disabled={line.quantity >= 99}
                          onClick={() => change(line, line.quantity + 1)}
                        >
                          +
                        </button>
                      </div>
                      <span className="dish-price">{formatPrice(line.total_price ?? 0)}</span>
                    </div>
                  ) : (
                    <div className="cart-line-footer">
                      <span className="caption">Сейчас недоступно</span>
                      <button type="button" className="text-button" onClick={() => change(line, 0)}>
                        Убрать
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {unavailable.length > 0 && (
            <p className="caption muted notice">Уберите недоступные позиции, чтобы оформить заказ.</p>
          )}
          {error && <p className="error-text">{error}</p>}
          <div className="cart-total">
            <span>Итого</span>
            <span aria-live="polite">{formatPrice(cart.total)}</span>
          </div>
          {onCheckout && (
            <MainAction text={`Оформить · ${formatPrice(cart.total)}`} disabled={unavailable.length > 0 || cart.count === 0} onClick={onCheckout} />
          )}
        </>
      )}
    </main>
  )
}
