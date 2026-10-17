import { createContext, useContext } from 'react'

import type { Cart } from '../api/types'

export interface CartState {
  cart: Cart | null
  /** Replace with what the server returned after a change. */
  set: (cart: Cart) => void
  reload: () => void
}

export const CartContext = createContext<CartState>({ cart: null, set: () => {}, reload: () => {} })

export const useCart = () => useContext(CartContext)
