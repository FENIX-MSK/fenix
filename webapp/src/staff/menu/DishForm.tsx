import { useState } from 'react'

import { api } from '../../api/client'
import type { DishInput, StaffCategory, StaffDish } from '../../api/types'
import { PhotoField } from './PhotoField'
import { kopecksToRubles, rublesToKopecks } from './rubles'
import { attempt } from './saveError'

interface SizeDraft {
  id: string | null
  name: string
  price: string
  portion: string
}

interface Props {
  dish: StaffDish | null
  categoryId: string
  categories: StaffCategory[]
  onDone: () => void
}

export function DishForm({ dish, categoryId, categories, onDone }: Props) {
  const [category, setCategory] = useState(dish?.category_id ?? categoryId)
  const [name, setName] = useState(dish?.name ?? '')
  const [description, setDescription] = useState(dish?.description ?? '')
  const [portion, setPortion] = useState(dish?.portion ?? '')
  const [hidden, setHidden] = useState(dish?.is_hidden ?? false)
  const [sizes, setSizes] = useState<SizeDraft[]>(
    dish?.sizes.map((s) => ({ id: s.id, name: s.name, price: kopecksToRubles(s.price), portion: s.portion ?? '' })) ?? [
      { id: null, name: '', price: '', portion: '' },
    ],
  )
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [photoUrl, setPhotoUrl] = useState(dish?.photo_url ?? null)

  const updateSize = (index: number, patch: Partial<SizeDraft>) =>
    setSizes(sizes.map((size, i) => (i === index ? { ...size, ...patch } : size)))

  const save = async () => {
    const prices = sizes.map((s) => rublesToKopecks(s.price))
    if (prices.some((p) => p === null)) return setError('Укажите цену в рублях, например 199 или 199,50')
    const body: DishInput = {
      category_id: category,
      name,
      description,
      portion: portion || null,
      is_hidden: hidden,
      sizes: sizes.map((s, i) => ({ id: s.id, name: s.name, price: prices[i] as number, portion: s.portion || null })),
    }
    setBusy(true)
    const failure = await attempt(() =>
      dish
        ? api.PUT('/api/v1/staff/dishes/{dish_id}', { params: { path: { dish_id: dish.id } }, body })
        : api.POST('/api/v1/staff/dishes', { body }),
    )
    setBusy(false)
    // On failure the form keeps everything typed (EXPERIENCE.md › State Patterns).
    if (failure) setError(failure)
    else onDone()
  }

  const remove = async () => {
    if (!dish) return
    if (!confirmDelete) return setConfirmDelete(true)
    const failure = await attempt(() => api.DELETE('/api/v1/staff/dishes/{dish_id}', { params: { path: { dish_id: dish.id } } }))
    if (failure) {
      setConfirmDelete(false)
      setError(failure)
    } else onDone()
  }

  return (
    <form
      className="editor-form"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      <h2 className="title staff-title">{dish ? 'Блюдо' : 'Новое блюдо'}</h2>
      {dish ? (
        <PhotoField dishId={dish.id} photoUrl={photoUrl} onChanged={setPhotoUrl} />
      ) : (
        <p className="caption muted">Фото можно добавить после сохранения блюда.</p>
      )}
      <label className="field">
        <span>Название</span>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={256} required />
      </label>
      <label className="field">
        <span>Категория</span>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Состав</span>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </label>
      <label className="field">
        <span>Вес / объём</span>
        <input value={portion} onChange={(e) => setPortion(e.target.value)} placeholder="190 г" />
      </label>

      <fieldset className="choice-group">
        <legend className="choice-legend">Размеры и цены</legend>
        {sizes.map((size, index) => (
          <div className="size-row" key={size.id ?? `new-${index}`}>
            <input
              aria-label="Название размера"
              placeholder={sizes.length > 1 ? 'Название' : 'Без названия'}
              value={size.name}
              onChange={(e) => updateSize(index, { name: e.target.value })}
            />
            <input
              aria-label="Цена, ₽"
              inputMode="decimal"
              placeholder="₽"
              value={size.price}
              onChange={(e) => updateSize(index, { price: e.target.value })}
            />
            <input
              aria-label="Объём размера"
              placeholder="объём"
              value={size.portion}
              onChange={(e) => updateSize(index, { portion: e.target.value })}
            />
            <button
              type="button"
              className="icon-button"
              aria-label="Удалить размер"
              disabled={sizes.length === 1}
              onClick={() => setSizes(sizes.filter((_, i) => i !== index))}
            >
              ✕
            </button>
          </div>
        ))}
        <button
          type="button"
          className="text-button"
          onClick={() => setSizes([...sizes, { id: null, name: '', price: '', portion: '' }])}
        >
          + Размер
        </button>
      </fieldset>

      <label className="toggle">
        <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
        <span>Скрыть от гостей</span>
      </label>
      {error && <p className="error-text">{error}</p>}
      <div className="button-row">
        <button type="submit" className="primary-button" disabled={busy}>
          Сохранить
        </button>
        <button type="button" className="secondary-button" onClick={onDone}>
          Отмена
        </button>
        {dish && (
          <button type="button" className="text-button danger-text" onClick={remove}>
            {confirmDelete ? 'Точно удалить?' : 'Удалить'}
          </button>
        )}
      </div>
    </form>
  )
}
