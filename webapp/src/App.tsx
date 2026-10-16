import { useEffect, useState } from 'react'

import { apiGet } from './api/client'
import { platform } from './platform'

type ApiStatus = 'checking' | 'ok' | 'unavailable'

export default function App() {
  const user = platform.getUser()
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    apiGet<{ status: string }>('/health')
      .then((body) => setApiStatus(body.status === 'ok' ? 'ok' : 'unavailable'))
      .catch(() => setApiStatus('unavailable'))
  }, [])

  return (
    <main className="app">
      <h1>Феникс бистро</h1>
      <p>{user ? `Привет, ${user.firstName}!` : 'Откройте приложение из Telegram-бота.'}</p>
      <p className="muted">
        Платформа: {platform.name} · API: {apiStatus}
      </p>
    </main>
  )
}
