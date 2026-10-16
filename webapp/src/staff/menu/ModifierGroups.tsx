import { useState } from 'react'

import { api } from '../../api/client'
import type { StaffCategory, StaffGroup } from '../../api/types'
import { formatPrice } from '../../guest/format'
import { useRemote } from '../../guest/useRemote'
import { GroupForm } from './GroupForm'

const loadGroups = () => api.GET('/api/v1/staff/modifier-groups')

function rule(group: StaffGroup): string {
  if (group.min_choice >= 1 && group.max_choice === 1) return 'обязательно, один из'
  if (group.min_choice >= 1) return `обязательно, ${group.min_choice}–${group.max_choice}`
  return group.max_choice === 1 ? 'по желанию, один из' : `по желанию, до ${group.max_choice}`
}

export function ModifierGroups({ categories, onChanged }: { categories: StaffCategory[]; onChanged: () => void }) {
  const { state, reload } = useRemote(loadGroups)
  const [editing, setEditing] = useState<StaffGroup | null | undefined>(undefined)

  if (editing !== undefined) {
    return (
      <GroupForm
        group={editing}
        categories={categories}
        onDone={() => {
          setEditing(undefined)
          reload()
          onChanged()
        }}
      />
    )
  }
  if (state.kind === 'loading') return <div className="skeleton" style={{ height: 160, marginTop: 16 }} />
  if (state.kind === 'error') return <p className="error-text">Не получилось загрузить группы.</p>

  return (
    <>
      <ul className="list">
        {state.data.map((group) => (
          <li key={group.id}>
            <button type="button" className="list-item" onClick={() => setEditing(group)}>
              <span>
                <strong>{group.name}</strong>
                <span className="caption muted">
                  {' '}
                  · {rule(group)} ·{' '}
                  {group.options.map((o) => (o.price_delta ? `${o.name} +${formatPrice(o.price_delta)}` : o.name)).join(', ')}
                </span>
              </span>
              <span aria-hidden="true">›</span>
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className="secondary-button add-button" onClick={() => setEditing(null)}>
        + Группа
      </button>
    </>
  )
}
