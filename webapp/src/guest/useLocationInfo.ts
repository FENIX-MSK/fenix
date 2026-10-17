import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { LocationInfo } from '../api/types'
import type { Remote } from './useRemote'

export type LocationState = Remote<LocationInfo>

// The waiting time follows the kitchen load: refreshed at least once a minute (FR-37).
const REFRESH_MS = 60_000

export function useLocationInfo(): { state: LocationState; reload: () => void } {
  const [state, setState] = useState<LocationState>({ kind: 'loading' })

  const load = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/v1/location')
      // A failed background refresh keeps what is on screen.
      if (data) setState({ kind: 'ready', data })
      else setState((s) => (s.kind === 'ready' ? s : { kind: 'error' }))
    } catch {
      setState((s) => (s.kind === 'ready' ? s : { kind: 'error' }))
    }
  }, [])

  useEffect(() => {
    const first = setTimeout(() => void load(), 0)
    const timer = setInterval(() => void load(), REFRESH_MS)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [load])

  const reload = useCallback(() => {
    setState({ kind: 'loading' })
    void load()
  }, [load])

  return { state, reload }
}
