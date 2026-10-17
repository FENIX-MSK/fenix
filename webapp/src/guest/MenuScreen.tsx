import { useCallback, useEffect, useState } from 'react'

import type { MenuCategory, MenuDish } from '../api/types'
import { CategoryCarousel } from './CategoryCarousel'
import { DishCard } from './DishCard'
import { SunMark } from './SunMark'
import { NETWORK_ERROR, RETRY } from './texts'
import type { MenuState } from './useMenu'

interface Props {
  menu: MenuState
  onRetry: () => void
  onOpenDish: (dish: MenuDish) => void
}

const sectionId = (categoryId: string) => `category-${categoryId}`

/** The category whose section is at the top of the viewport, under the sticky carousel. */
function useActiveCategory(categories: MenuCategory[]): [string | null, (id: string) => void] {
  const [activeId, setActiveId] = useState<string | null>(categories[0]?.id ?? null)

  useEffect(() => {
    if (categories.length === 0) return
    const order = categories.map((c) => c.id)
    // Entries only report sections whose state changed, so keep the full picture here.
    const intersecting = new Set<string>()

    const update = () => {
      const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2
      // Short sections at the end never reach the band; the bottom of the page means the last one.
      if (atBottom) return setActiveId(order[order.length - 1])
      const first = order.find((id) => intersecting.has(id))
      if (first) setActiveId(first)
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.getAttribute('data-category')
          if (!id) continue
          if (entry.isIntersecting) intersecting.add(id)
          else intersecting.delete(id)
        }
        update()
      },
      // A band just below the sticky carousel decides which section is current.
      { rootMargin: '-64px 0px -70% 0px' },
    )
    for (const id of order) {
      const element = document.getElementById(sectionId(id))
      if (element) observer.observe(element)
    }
    window.addEventListener('scroll', update, { passive: true })
    return () => {
      observer.disconnect()
      window.removeEventListener('scroll', update)
    }
  }, [categories])

  const select = useCallback((id: string) => {
    setActiveId(id)
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(sectionId(id))?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' })
  }, [])

  return [activeId, select]
}

export function MenuScreen({ menu, onRetry, onOpenDish }: Props) {
  if (menu.kind === 'loading') return <MenuSkeleton />
  if (menu.kind === 'error') {
    return (
      <div className="notice">
        <p>{NETWORK_ERROR}</p>
        <button type="button" className="secondary-button" onClick={onRetry}>
          {RETRY}
        </button>
      </div>
    )
  }
  return (
    <>
      {menu.data.promotions.length > 0 && (
        <div className="promo-banners">
          {menu.data.promotions.map((promotion) => (
            <p key={promotion.id} className="promo-banner">
              {promotion.title}
              {promotion.kind === 'checked' && <span className="caption"> · отметьте при оформлении</span>}
            </p>
          ))}
        </div>
      )}
      <MenuContent categories={menu.data.categories} onOpenDish={onOpenDish} />
    </>
  )
}

function MenuContent({ categories, onOpenDish }: { categories: MenuCategory[]; onOpenDish: (dish: MenuDish) => void }) {
  const [activeId, select] = useActiveCategory(categories)
  return (
    <>
      <CategoryCarousel categories={categories} activeId={activeId} onSelect={select} />
      {categories.map((category) => (
        <section
          key={category.id}
          id={sectionId(category.id)}
          data-category={category.id}
          className="menu-section"
          aria-labelledby={`${sectionId(category.id)}-title`}
        >
          <h2 className="section menu-section-title" id={`${sectionId(category.id)}-title`}>
            {category.name}
            {category.description && <span className="menu-section-note caption">{category.description}</span>}
          </h2>
          {category.dishes.length === 0 ? (
            <div className="empty">
              <SunMark size={40} />
              <p className="muted">Здесь пока пусто</p>
            </div>
          ) : (
            <div className="dish-grid">
              {category.dishes.map((dish) => (
                <DishCard key={dish.id} dish={dish} onOpen={onOpenDish} />
              ))}
            </div>
          )}
        </section>
      ))}
    </>
  )
}

function MenuSkeleton() {
  return (
    <div aria-busy="true" aria-label="Загружаем меню">
      <div className="carousel-list skeleton-row">
        {[72, 64, 80, 72].map((width, i) => (
          <div key={i} className="skeleton" style={{ width, height: 32, borderRadius: 9999, flex: 'none' }} />
        ))}
      </div>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="skeleton" style={{ height: 96, margin: '12px 0' }} />
      ))}
    </div>
  )
}
