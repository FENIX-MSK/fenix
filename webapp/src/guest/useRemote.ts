import { useCallback, useEffect, useState } from 'react'

export type Remote<T> = { kind: 'loading' } | { kind: 'ready'; data: T } | { kind: 'error' }

/** Load once on mount; `reload` retries after an error. Pass a stable (module-level) `load`. */
export function useRemote<T>(load: () => Promise<{ data?: T }>): { state: Remote<T>; reload: () => void } {
  const [state, setState] = useState<Remote<T>>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    load()
      .then(({ data }) => {
        if (!cancelled) setState(data === undefined ? { kind: 'error' } : { kind: 'ready', data })
      })
      .catch(() => {
        if (!cancelled) setState({ kind: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [load, attempt])

  const reload = useCallback(() => {
    setState({ kind: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  return { state, reload }
}
