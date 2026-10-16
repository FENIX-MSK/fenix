import { useState } from 'react'

import { api } from '../api/client'
import type { StaffMember } from '../api/types'
import { type Remote, useRemote } from '../guest/useRemote'
import { InviteCard } from './InviteCard'

const loadMembers = () => api.GET('/api/v1/staff/members')
const since = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

export function StaffMembersScreen() {
  const { state, reload } = useRemote(loadMembers)
  return (
    <>
      <h1 className="title staff-title">Сотрудники</h1>
      <MembersList state={state} onChanged={reload} />
      <InviteCard />
    </>
  )
}

function MembersList({ state, onChanged }: { state: Remote<StaffMember[]>; onChanged: () => void }) {
  if (state.kind === 'loading') return <div className="skeleton" style={{ height: 120, marginTop: 16 }} />
  if (state.kind === 'error') return <p className="error-text">Не получилось загрузить список.</p>
  return (
    <ul className="list">
      {state.data.map((member) => (
        <MemberRow key={member.user_id} member={member} onChanged={onChanged} />
      ))}
    </ul>
  )
}

function MemberRow({ member, onChanged }: { member: StaffMember; onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const name = [member.first_name, member.last_name].filter(Boolean).join(' ')

  const disable = async () => {
    // Irreversible for the colleague: the second tap confirms (EXPERIENCE.md).
    if (!confirming) return setConfirming(true)
    setConfirming(false)
    let code = 'network'
    try {
      const { error: failure } = await api.POST('/api/v1/staff/members/{user_id}/disable', {
        params: { path: { user_id: member.user_id } },
      })
      if (!failure) return onChanged()
      code = failure.error.code
    } catch {
      // A network failure is not a success: keep the row and say so.
    }
    setError(code === 'last_staff_member' ? 'Нельзя отключить последнего сотрудника' : 'Не сохранилось, попробуйте ещё раз')
  }

  return (
    <li className="member">
      <div>
        <div className="member-name">
          {name}
          {member.is_me && <span className="caption muted"> · это вы</span>}
        </div>
        <div className="caption muted">
          {member.username ? `@${member.username} · ` : ''}с {since.format(new Date(member.since))}
        </div>
        {error && <div className="caption error-text">{error}</div>}
      </div>
      <button type="button" className={confirming ? 'secondary-button danger' : 'text-button'} onClick={disable}>
        {confirming ? 'Точно отключить?' : 'Отключить'}
      </button>
    </li>
  )
}
