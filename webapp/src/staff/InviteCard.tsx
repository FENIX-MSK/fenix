import { useState } from 'react'

import { api } from '../api/client'
import type { Invitation } from '../api/types'
import { platform } from '../platform'

type State = { kind: 'idle' } | { kind: 'loading' } | { kind: 'ready'; invitation: Invitation } | { kind: 'error' }

const SHARE_TEXT = 'Приглашение в раздел персонала «Феникс бистро». Ссылка действует 24 часа.'

export function InviteCard() {
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [copied, setCopied] = useState(false)

  const create = async () => {
    setState({ kind: 'loading' })
    setCopied(false)
    const { data } = await api.POST('/api/v1/staff/invitations').catch(() => ({ data: undefined }))
    setState(data ? { kind: 'ready', invitation: data } : { kind: 'error' })
  }

  return (
    <section className="card">
      <h2 className="section">Пригласить сотрудника</h2>
      <p className="muted">Одноразовая ссылка в бот, действует 24 часа.</p>
      {state.kind === 'ready' ? (
        <>
          <p className="invite-url">{state.invitation.url}</p>
          <div className="button-row">
            <button
              type="button"
              className="primary-button"
              onClick={() =>
                platform.openTelegramLink(
                  `https://t.me/share/url?url=${encodeURIComponent(state.invitation.url)}&text=${encodeURIComponent(SHARE_TEXT)}`,
                )
              }
            >
              Отправить в Telegram
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                navigator.clipboard
                  ?.writeText(state.invitation.url)
                  .then(() => setCopied(true))
                  .catch(() => setCopied(false))
              }
            >
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
          </div>
        </>
      ) : (
        <button type="button" className="primary-button" disabled={state.kind === 'loading'} onClick={create}>
          {state.kind === 'loading' ? 'Создаём…' : 'Пригласить'}
        </button>
      )}
      {state.kind === 'error' && <p className="error-text">Не получилось создать ссылку, попробуйте ещё раз.</p>}
    </section>
  )
}
