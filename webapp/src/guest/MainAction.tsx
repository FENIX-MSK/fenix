import { useEffect, useRef } from 'react'

import { platform } from '../platform'

interface Props {
  text: string
  onClick: () => void
  disabled?: boolean
  loading?: boolean
}

const token = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

/** The screen's main action: Telegram's native MainButton, or a sticky button in a browser. */
export function MainAction({ text, onClick, disabled = false, loading = false }: Props) {
  const handler = useRef(onClick)
  useEffect(() => {
    handler.current = onClick
  })

  useEffect(() => {
    if (!platform.hasNativeMainButton) return
    return platform.showMainButton({
      text,
      enabled: !disabled && !loading,
      loading,
      color: token('--accent'),
      textColor: token('--on-accent'),
      onClick: () => handler.current(),
    })
  }, [text, disabled, loading])

  if (platform.hasNativeMainButton) return null
  return (
    <div className="main-action">
      <button type="button" className="primary-button" disabled={disabled || loading} onClick={onClick}>
        {loading ? '…' : text}
      </button>
    </div>
  )
}
