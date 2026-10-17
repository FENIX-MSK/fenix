import type { LocationInfo } from '../api/types'
import type { LocationState } from './useLocationInfo'
import { SunMark } from './SunMark'

interface Props {
  location: LocationState
  onAbout: () => void
  onHistory: () => void
  /** Only for staff members (FR-19). */
  onStaff?: () => void
}

function statusLine(info: LocationInfo): string {
  if (!info.status.is_open) return info.status.text
  if (info.orders_paused) return `${info.status.text} · заказы временно не принимаем`
  const wait = info.kitchen_busy ? `Кухня загружена · ≈${info.wait_minutes} мин` : `Готовим ≈${info.wait_minutes} мин`
  return `${info.status.text} · ${wait}`
}

export function Header({ location, onAbout, onHistory, onStaff }: Props) {
  return (
    <header className="header">
      <div className="header-brand">
        <SunMark />
        <div>
          <h1 className="display">Феникс</h1>
          <p className="caption muted header-status" aria-live="polite">
            {location.kind === 'ready' ? statusLine(location.data) : ' '}
          </p>
        </div>
      </div>
      <div className="header-actions">
      {onStaff && (
        <button type="button" className="text-button staff-entry" onClick={onStaff}>
          Персонал
        </button>
      )}
      <button type="button" className="icon-button" onClick={onHistory} aria-label="Мои заказы">
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path
            d="M6 3.5h12v17l-2-1.3-2 1.3-2-1.3-2 1.3-2-1.3-2 1.3z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M9 8.5h6M9 12h6M9 15.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      <button type="button" className="icon-button" onClick={onAbout} aria-label="О кафе">
        <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 10.5v6M12 7.5v.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
      </div>
    </header>
  )
}
