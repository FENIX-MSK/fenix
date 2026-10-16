import { useState } from 'react'

import { api } from '../../api/client'
import type { GroupInput, StaffCategory, StaffGroup } from '../../api/types'
import { kopecksToRubles, rublesToKopecks } from './rubles'
import { attempt } from './saveError'

interface OptionDraft {
  id: string | null
  name: string
  price: string
}

interface Props {
  group: StaffGroup | null
  categories: StaffCategory[]
  onDone: () => void
}

export function GroupForm({ group, categories, onDone }: Props) {
  const [name, setName] = useState(group?.name ?? '')
  const [min, setMin] = useState(String(group?.min_choice ?? 0))
  const [max, setMax] = useState(String(group?.max_choice ?? 1))
  const [options, setOptions] = useState<OptionDraft[]>(
    group?.options.map((o) => ({ id: o.id, name: o.name, price: o.price_delta ? kopecksToRubles(o.price_delta) : '' })) ?? [
      { id: null, name: '', price: '' },
    ],
  )
  const [dishIds, setDishIds] = useState(new Set(group?.dish_ids ?? []))
  const [categoryIds, setCategoryIds] = useState(new Set(group?.category_ids ?? []))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const toggle = (set: Set<string>, id: string, update: (next: Set<string>) => void) => {
    const next = new Set(set)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    update(next)
  }

  const save = async () => {
    const prices = options.map((o) => (o.price.trim() ? rublesToKopecks(o.price) : 0))
    if (prices.some((p) => p === null)) return setError('Доплата в рублях, например 30')
    const body: GroupInput = {
      name,
      min_choice: Number(min) || 0,
      max_choice: Number(max) || 1,
      options: options.map((o, i) => ({ id: o.id, name: o.name, price_delta: prices[i] as number })),
    }
    setBusy(true)
    let groupId = group?.id ?? null
    let failure: string | null
    if (group) {
      failure = await attempt(() =>
        api.PUT('/api/v1/staff/modifier-groups/{group_id}', { params: { path: { group_id: group.id } }, body }),
      )
    } else {
      failure = await attempt(async () => {
        const result = await api.POST('/api/v1/staff/modifier-groups', { body })
        groupId = result.data?.id ?? null
        return result
      })
    }
    if (!failure && groupId) {
      const id = groupId
      failure = await attempt(() =>
        api.PUT('/api/v1/staff/modifier-groups/{group_id}/links', {
          params: { path: { group_id: id } },
          body: { dish_ids: [...dishIds], category_ids: [...categoryIds] },
        }),
      )
    }
    setBusy(false)
    if (failure) setError(failure)
    else onDone()
  }

  const remove = async () => {
    if (!group) return
    if (!confirmDelete) return setConfirmDelete(true)
    const failure = await attempt(() =>
      api.DELETE('/api/v1/staff/modifier-groups/{group_id}', { params: { path: { group_id: group.id } } }),
    )
    if (failure) setError(failure)
    else onDone()
  }

  return (
    <form
      className="editor-form"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      <h2 className="title staff-title">{group ? 'Группа' : 'Новая группа'}</h2>
      <label className="field">
        <span>Название (видят гости)</span>
        <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Соус" />
      </label>
      <div className="size-row two">
        <label className="field">
          <span>Минимум</span>
          <input inputMode="numeric" value={min} onChange={(e) => setMin(e.target.value)} />
        </label>
        <label className="field">
          <span>Максимум</span>
          <input inputMode="numeric" value={max} onChange={(e) => setMax(e.target.value)} />
        </label>
      </div>
      <p className="caption muted">Минимум 1 — выбор обязателен; максимум 1 — «один из».</p>

      <fieldset className="choice-group">
        <legend className="choice-legend">Опции</legend>
        {options.map((option, index) => (
          <div className="size-row" key={option.id ?? `new-${index}`}>
            <input
              aria-label="Название опции"
              placeholder="Название"
              value={option.name}
              onChange={(e) => setOptions(options.map((o, i) => (i === index ? { ...o, name: e.target.value } : o)))}
            />
            <input
              aria-label="Доплата, ₽"
              inputMode="decimal"
              placeholder="+ ₽"
              value={option.price}
              onChange={(e) => setOptions(options.map((o, i) => (i === index ? { ...o, price: e.target.value } : o)))}
            />
            <span />
            <button
              type="button"
              className="icon-button"
              aria-label="Удалить опцию"
              disabled={options.length === 1}
              onClick={() => setOptions(options.filter((_, i) => i !== index))}
            >
              ✕
            </button>
          </div>
        ))}
        <button type="button" className="text-button" onClick={() => setOptions([...options, { id: null, name: '', price: '' }])}>
          + Опция
        </button>
      </fieldset>

      <fieldset className="choice-group">
        <legend className="choice-legend">Где предлагать</legend>
        {categories.map((category) => (
          <div key={category.id} className="link-category">
            <label className="toggle">
              <input
                type="checkbox"
                checked={categoryIds.has(category.id)}
                onChange={() => toggle(categoryIds, category.id, setCategoryIds)}
              />
              <span>
                <strong>{category.name}</strong> — все блюда
              </span>
            </label>
            {!categoryIds.has(category.id) &&
              category.dishes.map((dish) => (
                <label key={dish.id} className="toggle nested">
                  <input type="checkbox" checked={dishIds.has(dish.id)} onChange={() => toggle(dishIds, dish.id, setDishIds)} />
                  <span>{dish.name}</span>
                </label>
              ))}
          </div>
        ))}
      </fieldset>

      {error && <p className="error-text">{error}</p>}
      <div className="button-row">
        <button type="submit" className="primary-button" disabled={busy}>
          Сохранить
        </button>
        <button type="button" className="secondary-button" onClick={onDone}>
          Отмена
        </button>
        {group && (
          <button type="button" className="text-button danger-text" onClick={remove}>
            {confirmDelete ? 'Точно удалить?' : 'Удалить'}
          </button>
        )}
      </div>
    </form>
  )
}
