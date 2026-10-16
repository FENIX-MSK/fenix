import { useEffect } from 'react'

import type { LocationInfo } from '../api/types'
import { platform } from '../platform'
import { NETWORK_ERROR, RETRY } from './texts'
import type { LocationState } from './useLocationInfo'

const WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

interface Props {
  location: LocationState
  onBack: () => void
  onRetry: () => void
}

export function AboutScreen({ location, onBack, onRetry }: Props) {
  useEffect(() => platform.showBackButton(onBack), [onBack])

  return (
    <main className="screen about">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button about-back" onClick={onBack}>
          ← В меню
        </button>
      )}
      <h1 className="title about-title">О кафе</h1>
      {location.kind === 'loading' && <AboutSkeleton />}
      {location.kind === 'error' && (
        <div className="notice">
          <p>{NETWORK_ERROR}</p>
          <button type="button" className="secondary-button" onClick={onRetry}>
            {RETRY}
          </button>
        </div>
      )}
      {location.kind === 'ready' && <AboutContent location={location.data} />}
    </main>
  )
}

function AboutContent({ location }: { location: LocationInfo }) {
  const byWeekday = new Map(location.opening_hours.map((h) => [h.weekday, h]))
  return (
    <>
      <p className="about-status">{location.status.text}</p>
      {location.description && <p className="muted">{location.description}</p>}

      <section className="about-section" aria-labelledby="about-address">
        <h2 className="section" id="about-address">
          Адрес
        </h2>
        <p>{location.address}</p>
        <button type="button" className="secondary-button" onClick={() => platform.openLink(location.map_url)}>
          Открыть на карте
        </button>
      </section>

      <section className="about-section" aria-labelledby="about-hours">
        <h2 className="section" id="about-hours">
          Часы работы
        </h2>
        <dl className="hours">
          {WEEKDAYS.map((name, weekday) => {
            const hours = byWeekday.get(weekday)
            return (
              <div className="hours-row" key={name}>
                <dt>{name}</dt>
                <dd>{hours ? `${hours.opens_at}–${hours.closes_at}` : 'Выходной'}</dd>
              </div>
            )
          })}
        </dl>
      </section>

      <section className="about-section" aria-labelledby="about-contacts">
        <h2 className="section" id="about-contacts">
          Контакты
        </h2>
        <p>
          <a href={`tel:${location.phone.replace(/[^+\d]/g, '')}`}>{location.phone}</a>
        </p>
        <ul className="social">
          {location.social_links.map((link) => (
            <li key={link.url}>
              <button type="button" className="secondary-button" onClick={() => platform.openLink(link.url)}>
                {link.title}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}

function AboutSkeleton() {
  return (
    <div aria-hidden="true">
      <div className="skeleton" style={{ height: 20, width: '60%', margin: '16px 0' }} />
      <div className="skeleton" style={{ height: 96, margin: '16px 0' }} />
      <div className="skeleton" style={{ height: 180, margin: '16px 0' }} />
    </div>
  )
}
