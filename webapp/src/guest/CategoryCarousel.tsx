import { useEffect, useRef } from 'react'

import type { MenuCategory } from '../api/types'

interface Props {
  categories: MenuCategory[]
  activeId: string | null
  onSelect: (id: string) => void
}

export function CategoryCarousel({ categories, activeId, onSelect }: Props) {
  const listRef = useRef<HTMLDivElement>(null)

  // Keep the active chip in view as the page scrolls (horizontal only).
  useEffect(() => {
    const list = listRef.current
    const chip = list?.querySelector<HTMLElement>(`[data-id="${activeId}"]`)
    if (!list || !chip) return
    const left = chip.offsetLeft - (list.clientWidth - chip.clientWidth) / 2
    list.scrollTo({ left, behavior: 'smooth' })
  }, [activeId])

  return (
    <nav className="carousel" aria-label="Категории">
      <div className="carousel-list" ref={listRef}>
        {categories.map((category) => (
          <button
            key={category.id}
            type="button"
            data-id={category.id}
            className={category.id === activeId ? 'chip selected' : 'chip'}
            aria-current={category.id === activeId ? 'true' : undefined}
            onClick={() => onSelect(category.id)}
          >
            {category.name}
          </button>
        ))}
      </div>
    </nav>
  )
}
