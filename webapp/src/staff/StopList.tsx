import { useState } from 'react'

import { api } from '../api/client'
import type { StopList as StopListData } from '../api/types'
import { useRemote } from '../guest/useRemote'
import { platform } from '../platform'

const loadStopList = () => api.GET('/api/v1/staff/stop-list')

type Target = { size_id: string } | { modifier_id: string }

export function StopList() {
  const { state } = useRemote(loadStopList)
  if (state.kind === 'loading') return <div className="skeleton" style={{ height: 240, marginTop: 16 }} />
  if (state.kind === 'error') return <p className="error-text">Не получилось загрузить стоп-лист.</p>
  return <StopListContent initial={state.data} />
}

function StopListContent({ initial }: { initial: StopListData }) {
  const [data, setData] = useState(initial)
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)

  const apply = (id: string, stopped: boolean, source: StopListData): StopListData => ({
    dishes: source.dishes.map((d) => ({ ...d, sizes: d.sizes.map((s) => (s.id === id ? { ...s, stopped } : s)) })),
    groups: source.groups.map((g) => ({ ...g, modifiers: g.modifiers.map((m) => (m.id === id ? { ...m, stopped } : m)) })),
  })

  const toggle = async (target: Target, id: string, stopped: boolean) => {
    // Optimistic: the switch moves at once and rolls back if the server says no.
    const before = data
    setData(apply(id, stopped, data))
    setError(null)
    platform.haptic('selection')
    try {
      const { error: failure } = await api.PUT('/api/v1/staff/stop-list', { body: { ...target, stopped } })
      if (!failure) return
    } catch {
      // handled below
    }
    setData(before)
    setError('Не сохранилось, попробуйте ещё раз')
  }

  const needle = query.trim().toLowerCase()
  const matches = (text: string) => !needle || text.toLowerCase().includes(needle)
  const dishes = data.dishes.filter((d) => matches(d.name) || matches(d.category) || d.sizes.some((s) => matches(s.name)))
  const groups = data.groups
    .map((g) => ({ ...g, modifiers: g.modifiers.filter((m) => matches(m.name) || matches(g.name)) }))
    .filter((g) => g.modifiers.length > 0)

  return (
    <>
      <h1 className="title staff-title">Стоп-лист</h1>
      <input
        className="search"
        type="search"
        placeholder="Поиск: молоко, фри…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Поиск по блюдам и модификаторам"
      />
      {error && <p className="error-text">{error}</p>}
      <ul className="list stop-list">
        {groups.map((group) =>
          group.modifiers.map((modifier) => (
            <Switch
              key={modifier.id}
              title={modifier.name}
              caption={`Модификатор · ${group.name}`}
              stopped={modifier.stopped}
              onChange={(stopped) => toggle({ modifier_id: modifier.id }, modifier.id, stopped)}
            />
          )),
        )}
        {dishes.map((dish) =>
          dish.sizes.map((size) => (
            <Switch
              key={size.id}
              title={size.name ? `${dish.name} · ${size.name}` : dish.name}
              caption={`${dish.category}${dish.is_hidden ? ' · скрыто' : ''}`}
              stopped={size.stopped}
              onChange={(stopped) => toggle({ size_id: size.id }, size.id, stopped)}
            />
          )),
        )}
      </ul>
      {dishes.length === 0 && groups.length === 0 && <p className="muted notice">Ничего не нашлось</p>}
    </>
  )
}

function Switch({ title, caption, stopped, onChange }: { title: string; caption: string; stopped: boolean; onChange: (stopped: boolean) => void }) {
  return (
    <li>
      <label className="stop-row">
        <span>
          <span className={stopped ? 'stop-name stopped' : 'stop-name'}>{title}</span>
          <span className="caption muted">
            {caption}
            {stopped ? ' · закончилось' : ''}
          </span>
        </span>
        {/* On = in stock, as people say «включить обратно». */}
        <input type="checkbox" role="switch" className="switch" checked={!stopped} onChange={(e) => onChange(!e.target.checked)} />
      </label>
    </li>
  )
}
