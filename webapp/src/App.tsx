import { lazy, Suspense, useCallback, useEffect, useState } from 'react'

import type { MenuDish } from './api/types'
import { AboutScreen } from './guest/AboutScreen'
import { CartBar } from './guest/CartBar'
import { CartScreen } from './guest/CartScreen'
import { CheckoutScreen } from './guest/CheckoutScreen'
import { DishSheet } from './guest/DishSheet'
import { Header } from './guest/Header'
import { MenuScreen } from './guest/MenuScreen'
import { useLocationInfo } from './guest/useLocationInfo'
import { useMe } from './guest/useMe'
import { useMenu } from './guest/useMenu'
import { platform } from './platform'

type Screen = 'menu' | 'about' | 'staff' | 'cart' | 'checkout'

const StaffApp = lazy(() => import('./staff/StaffApp'))

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
  const { state: me } = useMe()
  const isStaff = me.kind === 'ready' && me.data.is_staff
  const openMenu = useCallback(() => setScreen('menu'), [])
  const [openDish, setOpenDish] = useState<MenuDish | null>(null)
  const closeDish = useCallback(() => setOpenDish(null), [])

  if (screen === 'staff' && isStaff) {
    return (
      <Suspense fallback={<div className="screen" aria-busy="true" />}>
        <StaffApp onExit={openMenu} />
      </Suspense>
    )
  }
  if (screen === 'cart') return <CartScreen onBack={openMenu} onCheckout={() => setScreen('checkout')} />
  if (screen === 'checkout') return <CheckoutScreen onBack={() => setScreen('cart')} />
  if (screen === 'about') {
    return <AboutScreen location={location} onBack={openMenu} onRetry={reloadLocation} />
  }
  return (
    <div className="screen">
      <Header
        location={location}
        onAbout={() => setScreen('about')}
        onStaff={isStaff ? () => setScreen('staff') : undefined}
      />
      <main>
        <MenuScreen menu={menu} onRetry={reloadMenu} onOpenDish={setOpenDish} />
      </main>
      {!openDish && <CartBar onOpen={() => setScreen('cart')} />}
      {openDish && <DishSheet dish={openDish} onClose={closeDish} />}
    </div>
  )
}
