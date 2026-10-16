import { useCallback, useEffect, useState } from 'react'

import { AboutScreen } from './guest/AboutScreen'
import { Header } from './guest/Header'
import { useLocationInfo } from './guest/useLocationInfo'
import { platform } from './platform'

type Screen = 'menu' | 'about'

function useTheme() {
  useEffect(() => {
    const dark = platform.isDark()
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    // The messenger's header matches the screen background (EXPERIENCE.md › Responsive).
    platform.setColors(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim())
  }, [])
}

export default function App() {
  useTheme()
  const [screen, setScreen] = useState<Screen>('menu')
  const { state: location, reload } = useLocationInfo()
  const openMenu = useCallback(() => setScreen('menu'), [])

  if (screen === 'about') {
    return <AboutScreen location={location} onBack={openMenu} onRetry={reload} />
  }
  return (
    <div className="screen">
      <Header location={location} onAbout={() => setScreen('about')} />
      <main className="menu-placeholder muted">Меню появится здесь.</main>
    </div>
  )
}
