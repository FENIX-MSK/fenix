import { type ReactNode, useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Cart } from '../api/types'
import { CartContext } from './cart'

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, set] = useState<Cart | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    api
      .GET('/api/v1/cart')
      .then(({ data }) => {
        if (!cancelled && data) set(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  return <CartContext.Provider value={{ cart, set, reload }}>{children}</CartContext.Provider>
}
