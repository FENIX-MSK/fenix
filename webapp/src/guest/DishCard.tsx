import type { MenuDish } from '../api/types'
import { formatPrice } from './format'
import { SunMark } from './SunMark'

interface Props {
  dish: MenuDish
  onOpen: (dish: MenuDish) => void
}

export function DishCard({ dish, onOpen }: Props) {
  const meta = [dish.portion, dish.description].filter(Boolean).join(' · ')
  return (
    <button
      type="button"
      className={dish.sold_out ? 'dish-card sold-out' : 'dish-card'}
      // Sold out: visible, labelled, but not openable (FR-3).
      disabled={dish.sold_out}
      onClick={() => onOpen(dish)}
    >
      <span className="dish-photo" aria-hidden="true">
        {dish.photo_url ? <img src={dish.photo_url} alt="" loading="lazy" /> : <SunMark size={36} />}
      </span>
      <span className="dish-body">
        <span className="dish-name">{dish.name}</span>
        {meta && <span className="dish-meta caption muted">{meta}</span>}
        <span className="dish-footer">
          <span className="dish-price">
            {dish.discount_percent > 0 && (
              <s className="old-price">{formatPrice(dish.original_price_from, dish.has_sizes)}</s>
            )}
            {formatPrice(dish.price_from, dish.has_sizes)}
          </span>
          {dish.sold_out && <span className="sold-out-badge caption">Закончилось</span>}
        </span>
      </span>
    </button>
  )
}
