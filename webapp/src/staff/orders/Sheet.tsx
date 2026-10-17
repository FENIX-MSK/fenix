import { type ReactNode, useEffect, useRef } from 'react'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
}

/** A plain bottom sheet (a centred modal on tablets) for staff dialogs. */
export function Sheet({ title, onClose, children }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div
        className="sheet staff-sheet"
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="staff-sheet-head">
          <h2 className="sheet-title">{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
