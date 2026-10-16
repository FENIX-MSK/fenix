import { useCallback, useEffect, useState } from 'react'

import type { MenuDish } from './api/types'
import { AboutScreen } from './guest/AboutScreen'
import { DishSheet } from './guest/DishSheet'
import { Header } from './guest/Header'
import { MenuScreen } from './guest/MenuScreen'
import { useLocationInfo } from './guest/useLocationInfo'
import { useMenu } from './guest/useMenu'
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
  const { state: location, reload: reloadLocation } = useLocationInfo()
  const { state: menu, reload: reloadMenu } = useMenu()
  const openMenu = useCallback(() => setScreen('menu'), [])
  const [openDish, setOpenDish] = useState<MenuDish | null>(null)
  const closeDish = useCallback(() => setOpenDish(null), [])

  if (screen === 'about') {
    return <AboutScreen location={location} onBack={openMenu} onRetry={reloadLocation} />
  }
  return (
    <div className="screen">
      <Header location={location} onAbout={() => setScreen('about')} />
      <main>
        <MenuScreen menu={menu} onRetry={reloadMenu} onOpenDish={setOpenDish} />
      </main>
      {openDish && <DishSheet dish={openDish} onClose={closeDish} />}
    </div>
  )
}
