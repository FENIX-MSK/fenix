import { useEffect, useRef } from 'react'

import { platform } from '../platform'

export interface Signal {
  event: string
  order_id?: string
  status?: string | null
  version?: number | null
}

// Close codes from the server that retrying cannot fix (bad launch data, not allowed).
const FINAL_CODES = new Set([4400, 4401, 4403])
const MAX_DELAY_MS = 15_000

/**
 * Listen to server signals on `channel` ("staff" or "order:<id>"); AD-5. A signal only
 * says something changed — the caller re-reads through REST. After a dropped connection
 * the hook reconnects and reports `{ event: 'reconnected' }`, since signals may have been
 * missed meanwhile.
 */
export function useSignals(channel: string | null, onSignal: (signal: Signal) => void): void {
  const handler = useRef(onSignal)
  useEffect(() => {
    handler.current = onSignal
  }, [onSignal])

  useEffect(() => {
    if (!channel) return
    let socket: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let attempt = 0
    let stopped = false

    const connect = () => {
      const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws`
      socket = new WebSocket(url)
      socket.onopen = () => {
        socket?.send(JSON.stringify({ auth: platform.getInitDataRaw() ?? '', channel }))
      }
      socket.onmessage = (message) => {
        let signal: Signal
        try {
          signal = JSON.parse(String(message.data)) as Signal
        } catch {
          return
        }
        if (signal.event === 'ping') return
        if (signal.event === 'subscribed') {
          if (attempt > 0) handler.current({ event: 'reconnected' })
          attempt = 0
          return
        }
        handler.current(signal)
      }
      socket.onclose = (event) => {
        if (stopped || FINAL_CODES.has(event.code)) return
        attempt += 1
        const delay = Math.min(1000 * 2 ** (attempt - 1), MAX_DELAY_MS)
        timer = setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(timer)
      socket?.close()
    }
  }, [channel])
}
