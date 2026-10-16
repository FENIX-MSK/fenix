import { type ReactNode, useEffect, useState } from 'react'

import { platform } from '../platform'
import { MenuEditor } from './menu/MenuEditor'
import { MoreScreen, type MoreSection } from './MoreScreen'
import { Placeholder } from './Placeholder'
import { StopList } from './StopList'

type Tab = 'orders' | 'stop-list' | 'menu' | 'more'

const TABS: { id: Tab; label: string }[] = [
  { id: 'orders', label: 'Заказы' },
  { id: 'stop-list', label: 'Стоп-лист' },
  { id: 'menu', label: 'Меню' },
  { id: 'more', label: 'Ещё' },
]

interface Props {
  onExit: () => void
}

/** The staff section: lazy-loaded, so guests never download it (EXPERIENCE.md › IA). */
export default function StaffApp({ onExit }: Props) {
  const [tab, setTab] = useState<Tab>('orders')
  const [section, setSection] = useState<MoreSection | null>(null)

  // Back: from a sub-section to «Ещё», from the section to the guest menu.
  useEffect(() => platform.showBackButton(section ? () => setSection(null) : onExit), [section, onExit])

  let content: ReactNode
  if (tab === 'more') content = <MoreScreen section={section} onOpen={setSection} />
  else if (tab === 'orders') content = <Placeholder title="Заказы" text="Новых заказов нет" />
  else if (tab === 'stop-list') content = <StopList />
  else content = <MenuEditor />

  return (
    <div className="staff">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button" onClick={section ? () => setSection(null) : onExit}>
          ← {section ? 'Назад' : 'К меню гостя'}
        </button>
      )}
      <main className="staff-main">{content}</main>
      <nav className="bottom-nav" aria-label="Раздел персонала">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={item.id === tab ? 'bottom-nav-item active' : 'bottom-nav-item'}
            aria-current={item.id === tab ? 'page' : undefined}
            onClick={() => {
              setTab(item.id)
              setSection(null)
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
