import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { PriceResult } from '../api/types'

export interface Selection {
  dishId: string
  sizeId: string | null
  modifierIds: string[]
  quantity: number
}

type Outcome =
  | { kind: 'ready'; price: PriceResult }
  | { kind: 'invalid'; reason: string }
  | { kind: 'error' }

export type PriceState = { kind: 'idle' } | { kind: 'pending' } | Outcome

/**
 * The total always comes from the server (AD-6). Every change cancels the request in
 * flight; an answer counts only for the selection it was asked for, so an old figure is
 * never shown while a new one is on its way.
 */
export function useDishPrice(selection: Selection): PriceState {
  const { dishId, sizeId, quantity } = selection
  const modifierKey = selection.modifierIds.join(',')
  const key = `${dishId}|${sizeId}|${modifierKey}|${quantity}`
  const [answer, setAnswer] = useState<{ key: string; outcome: Outcome } | null>(null)

  useEffect(() => {
    if (!sizeId) return
    const controller = new AbortController()
    const settle = (outcome: Outcome) => {
      if (!controller.signal.aborted) setAnswer({ key, outcome })
    }
    api
      .POST('/api/v1/menu/price', {
        body: {
          dish_id: dishId,
          size_id: sizeId,
          modifier_ids: modifierKey ? modifierKey.split(',') : [],
          quantity,
        },
        signal: controller.signal,
      })
      .then(({ data, error }) => {
        if (data) settle({ kind: 'ready', price: data })
        else if (error?.error.code === 'invalid_selection') {
          settle({ kind: 'invalid', reason: String(error.error.details?.reason ?? '') })
        } else settle({ kind: 'error' })
      })
      .catch(() => settle({ kind: 'error' }))
    return () => controller.abort()
  }, [key, dishId, sizeId, modifierKey, quantity])

  if (!sizeId) return { kind: 'idle' }
  if (answer?.key !== key) return { kind: 'pending' }
  return answer.outcome
}
