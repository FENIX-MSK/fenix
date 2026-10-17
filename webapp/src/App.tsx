import { lazy, Suspense, useCallback, useEffect, useState } from 'react'

import { api } from './api/client'
import type { MenuDish, Order } from './api/types'
import { AboutScreen } from './guest/AboutScreen'
import { ActiveOrderBanner } from './guest/ActiveOrderBanner'
import { CartBar } from './guest/CartBar'
import { CartScreen } from './guest/CartScreen'
import { CheckoutScreen, type PlaceOrder } from './guest/CheckoutScreen'
import { DishSheet } from './guest/DishSheet'
import { Header } from './guest/Header'
import { HistoryScreen } from './guest/HistoryScreen'
import { MenuScreen } from './guest/MenuScreen'
import { OrderScreen } from './guest/OrderScreen'
import { orderErrorText } from './guest/orderTexts'
import { useCart } from './guest/cart'
import { useLocationInfo } from './guest/useLocationInfo'
import { useMe } from './guest/useMe'
import { useMenu } from './guest/useMenu'
import { platform } from './platform'

type Screen = 'menu' | 'about' | 'staff' | 'cart' | 'checkout' | 'order' | 'history'

const StaffApp = lazy(() => import('./staff/StaffApp'))

function useTheme() {
  useEffect(() => {
    const dark = platform.isDark()
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    // The messenger's header matches the screen background (EXPERIENCE.md › Responsive).
    platform.setColors(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim())
  }, [])
}

// Deep links: `?order=<id>` from a chat button opens that order; `&staff=1` on the board.
const launch = new URLSearchParams(window.location.search)
const LINKED_ORDER = launch.get('order')
const LINKED_FOR_STAFF = launch.get('staff') === '1'

export default function App() {
  useTheme()
  const [screen, setScreen] = useState<Screen>(LINKED_ORDER ? (LINKED_FOR_STAFF ? 'staff' : 'order') : 'menu')
  const { state: location, reload: reloadLocation } = useLocationInfo()
  const { state: menu, reload: reloadMenu } = useMenu()
  const { state: me } = useMe()
  const isStaff = me.kind === 'ready' && me.data.is_staff
  const openMenu = useCallback(() => setScreen('menu'), [])
  const [openDish, setOpenDish] = useState<MenuDish | null>(null)
  const closeDish = useCallback(() => setOpenDish(null), [])
  const [order, setOrder] = useState<{ id: string; initial?: Order } | null>(
    LINKED_ORDER && !LINKED_FOR_STAFF ? { id: LINKED_ORDER } : null,
  )
  const { reload: reloadCart } = useCart()
  const [skipped, setSkipped] = useState<string[]>([])
  const openOrder = useCallback((placed: Order) => {
    setOrder({ id: placed.id, initial: placed })
    setScreen('order')
  }, [])

  const placeOrder = useCallback(
    async ({ paymentMethod, comment }: PlaceOrder): Promise<string | null> => {
      try {
        const { data, error } = await api.POST('/api/v1/orders', { body: { payment_method: paymentMethod, comment } })
        if (!data) {
          reloadCart()
          return orderErrorText(error?.error.code)
        }
        platform.haptic('success')
        setOrder({ id: data.id, initial: data })
        reloadCart()
        setScreen('order')
        return null
      } catch {
        return orderErrorText(undefined)
      }
    },
    [reloadCart],
  )

  if (screen === 'staff' && isStaff) {
    return (
      <Suspense fallback={<div className="screen" aria-busy="true" />}>
        <StaffApp onExit={openMenu} openOrderId={LINKED_FOR_STAFF ? LINKED_ORDER : null} />
      </Suspense>
    )
  }
  // Waiting to learn whether the user is staff before falling back to the menu.
  if (screen === 'staff' && me.kind === 'loading') return <div className="screen" aria-busy="true" />
  if (screen === 'cart') {
    return (
      <CartScreen
        onBack={() => {
          setSkipped([])
          openMenu()
        }}
        onCheckout={() => setScreen('checkout')}
        skipped={skipped}
      />
    )
  }
  if (screen === 'history') {
    return (
      <HistoryScreen
        onBack={openMenu}
        onOpen={openOrder}
        onRepeated={(names) => {
          setSkipped(names)
          setScreen('cart')
        }}
      />
    )
  }
  if (screen === 'checkout') return <CheckoutScreen onBack={() => setScreen('cart')} onPlace={placeOrder} />
  if (screen === 'order' && order) return <OrderScreen orderId={order.id} initial={order.initial} onBack={openMenu} />
  if (screen === 'about') {
    return <AboutScreen location={location} onBack={openMenu} onRetry={reloadLocation} />
  }
  return (
    <div className="screen">
      <Header
        location={location}
        onAbout={() => setScreen('about')}
        onHistory={() => setScreen('history')}
        onStaff={isStaff ? () => setScreen('staff') : undefined}
      />
      <ActiveOrderBanner onOpen={openOrder} />
      <main>
        <MenuScreen menu={menu} onRetry={reloadMenu} onOpenDish={setOpenDish} />
      </main>
      {!openDish && <CartBar onOpen={() => setScreen('cart')} />}
      {openDish && <DishSheet dish={openDish} onClose={closeDish} />}
    </div>
  )
}
