import { useState } from 'react'

import { api } from '../../api/client'
import type { StaffCategory, StaffDish } from '../../api/types'
import { formatPrice } from '../../guest/format'
import { useRemote } from '../../guest/useRemote'
import { CategoryForm } from './CategoryForm'
import { DishForm } from './DishForm'
import { ModifierGroups } from './ModifierGroups'

type Editing =
  | { kind: 'category'; category: StaffCategory | null }
  | { kind: 'dish'; dish: StaffDish | null; categoryId: string }

const loadCatalog = () => api.GET('/api/v1/staff/catalog')

function move<T>(items: T[], index: number, delta: number): T[] {
  const next = [...items]
  const [item] = next.splice(index, 1)
  next.splice(index + delta, 0, item)
  return next
}

export function MenuEditor() {
  const { state, reload } = useRemote(loadCatalog)
  const [editing, setEditing] = useState<Editing | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [view, setView] = useState<'dishes' | 'groups'>('dishes')

  if (state.kind === 'loading') return <div className="skeleton" style={{ height: 240, marginTop: 16 }} />
  if (state.kind === 'error') return <p className="error-text">Не получилось загрузить меню.</p>
  const categories = state.data.categories

  const done = () => {
    setEditing(null)
    reload()
  }
  if (editing?.kind === 'category') return <CategoryForm category={editing.category} onDone={done} />
  if (editing?.kind === 'dish') {
    return <DishForm dish={editing.dish} categoryId={editing.categoryId} categories={categories} onDone={done} />
  }

  const tabs = (
    <div className="segmented" role="tablist">
      {(['dishes', 'groups'] as const).map((id) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={view === id}
          className={view === id ? 'segment active' : 'segment'}
          onClick={() => setView(id)}
        >
          {id === 'dishes' ? 'Блюда' : 'Модификаторы'}
        </button>
      ))}
    </div>
  )
  if (view === 'groups') {
    return (
      <>
        <h1 className="title staff-title">Меню</h1>
        {tabs}
        <ModifierGroups categories={categories} onChanged={reload} />
      </>
    )
  }

  const reorderCategories = async (index: number, delta: number) => {
    const ids = move(categories, index, delta).map((c) => c.id)
    await api.POST('/api/v1/staff/categories/order', { body: { ids } }).catch(() => undefined)
    reload()
  }
  const reorderDishes = async (category: StaffCategory, index: number, delta: number) => {
    const ids = move(category.dishes, index, delta).map((d) => d.id)
    await api.POST('/api/v1/staff/dishes/order', { body: { category_id: category.id, ids } }).catch(() => undefined)
    reload()
  }

  return (
    <>
      <h1 className="title staff-title">Меню</h1>
      {tabs}
      <ul className="editor-list">
        {categories.map((category, index) => (
          <li key={category.id} className="editor-category">
            <div className="editor-row">
              <button
                type="button"
                className="editor-name"
                aria-expanded={openId === category.id}
                onClick={() => setOpenId(openId === category.id ? null : category.id)}
              >
                {category.name}
                <span className="caption muted">
                  {' '}
                  · {category.dishes.length}
                  {category.is_hidden && ' · скрыта'}
                </span>
              </button>
              <Arrows
                onUp={index > 0 ? () => reorderCategories(index, -1) : undefined}
                onDown={index < categories.length - 1 ? () => reorderCategories(index, 1) : undefined}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={`Изменить категорию ${category.name}`}
                onClick={() => setEditing({ kind: 'category', category })}
              >
                ✎
              </button>
            </div>
            {openId === category.id && (
              <ul className="editor-dishes">
                {category.dishes.map((dish, dishIndex) => (
                  <li key={dish.id} className="editor-row">
                    <button
                      type="button"
                      className="editor-name"
                      onClick={() => setEditing({ kind: 'dish', dish, categoryId: category.id })}
                    >
                      {dish.name}
                      <span className="caption muted">
                        {' '}
                        · {dish.sizes.map((s) => formatPrice(s.price)).join(' / ')}
                        {dish.is_hidden && ' · скрыто'}
                      </span>
                    </button>
                    <Arrows
                      onUp={dishIndex > 0 ? () => reorderDishes(category, dishIndex, -1) : undefined}
                      onDown={
                        dishIndex < category.dishes.length - 1 ? () => reorderDishes(category, dishIndex, 1) : undefined
                      }
                    />
                  </li>
                ))}
                <li>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => setEditing({ kind: 'dish', dish: null, categoryId: category.id })}
                  >
                    + Блюдо
                  </button>
                </li>
              </ul>
            )}
          </li>
        ))}
      </ul>
      <button type="button" className="secondary-button add-button" onClick={() => setEditing({ kind: 'category', category: null })}>
        + Категория
      </button>
    </>
  )
}

function Arrows({ onUp, onDown }: { onUp?: () => void; onDown?: () => void }) {
  return (
    <>
      <button type="button" className="icon-button" aria-label="Выше" disabled={!onUp} onClick={onUp}>
        ↑
      </button>
      <button type="button" className="icon-button" aria-label="Ниже" disabled={!onDown} onClick={onDown}>
        ↓
      </button>
    </>
  )
}
