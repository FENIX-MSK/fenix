import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { LocationInfo } from '../api/types'

export type LocationState =
  | { kind: 'loading' }
  | { kind: 'ready'; location: LocationInfo }
  | { kind: 'error' }

export function useLocationInfo(): { state: LocationState; reload: () => void } {
  const [state, setState] = useState<LocationState>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    api
      .GET('/api/v1/location')
      .then(({ data }) => {
        if (cancelled) return
        setState(data ? { kind: 'ready', location: data } : { kind: 'error' })
      })
      .catch(() => {
        if (!cancelled) setState({ kind: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [attempt])

  const reload = useCallback(() => {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  return { state, reload }
}
