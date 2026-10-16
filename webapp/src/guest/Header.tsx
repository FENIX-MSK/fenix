import type { LocationState } from './useLocationInfo'
import { SunMark } from './SunMark'

interface Props {
  location: LocationState
  onAbout: () => void
  /** Only for staff members (FR-19). */
  onStaff?: () => void
}

export function Header({ location, onAbout, onStaff }: Props) {
  return (
    <header className="header">
      <div className="header-brand">
        <SunMark />
        <div>
          <h1 className="display">Феникс</h1>
          <p className="caption muted header-status" aria-live="polite">
            {location.kind === 'ready' ? location.data.status.text : ' '}
          </p>
        </div>
      </div>
      <div className="header-actions">
      {onStaff && (
        <button type="button" className="text-button staff-entry" onClick={onStaff}>
          Персонал
        </button>
      )}
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
