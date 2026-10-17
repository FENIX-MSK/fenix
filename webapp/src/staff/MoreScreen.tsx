import { CafeScreen } from './CafeScreen'
import { OrderSettingsScreen } from './OrderSettingsScreen'
import { StaffMembersScreen } from './StaffMembersScreen'

export type MoreSection = 'cafe' | 'orders' | 'members'

const SECTIONS: { id: MoreSection; label: string }[] = [
  { id: 'orders', label: 'Приём заказов, доставка, параметры' },
  { id: 'cafe', label: 'Кафе: часы, контакты, фото' },
  { id: 'members', label: 'Сотрудники' },
]

interface Props {
  section: MoreSection | null
  onOpen: (section: MoreSection) => void
}

export function MoreScreen({ section, onOpen }: Props) {
  if (section === 'members') return <StaffMembersScreen />
  if (section === 'cafe') return <CafeScreen />
  if (section === 'orders') return <OrderSettingsScreen />
  return (
    <>
      <h1 className="title staff-title">Ещё</h1>
      <ul className="list">
        {SECTIONS.map((item) => (
          <li key={item.id}>
            <button type="button" className="list-item" onClick={() => onOpen(item.id)}>
              <span>{item.label}</span>
              <span aria-hidden="true">›</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}
