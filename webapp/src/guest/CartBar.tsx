import { useCart } from './cart'
import { formatPrice } from './format'

/** «Корзина · N ₽» at the bottom of the menu (DESIGN.md › cart-bar). */
export function CartBar({ onOpen }: { onOpen: () => void }) {
  const { cart } = useCart()
  if (!cart || cart.lines.length === 0) return null
  return (
    <button type="button" className="cart-bar" onClick={onOpen}>
      <span>Корзина</span>
      <span>{formatPrice(cart.total)}</span>
    </button>
  )
}
