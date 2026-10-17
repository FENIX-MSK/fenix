import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Promotion, StaffCategory } from '../api/types'

type Draft = Omit<Promotion, 'id'> & { id?: string }

const EMPTY: Draft = {
  title: '',
  percent: 10,
  category_id: null,
  starts_on: null,
  ends_on: null,
  kind: 'auto',
  enabled: true,
}

const MESSAGES: Record<string, string> = {
  bad_dates: 'Дата окончания раньше начала',
  title_required: 'Нужен текст для гостей',
  bad_percent: 'Процент от 1 до 100',
}

/** «Акции» (FR-32). */
export function PromotionsScreen() {
  const [items, setItems] = useState<Promotion[] | null>(null)
  const [categories, setCategories] = useState<StaffCategory[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const { data } = await api.GET('/api/v1/staff/promotions')
      if (data) setItems(data)
    } catch {
      setError('Не получилось загрузить акции.')
    }
  }, [])

  useEffect(() => {
    const first = setTimeout(() => void load(), 0)
    api
      .GET('/api/v1/staff/catalog')
      .then(({ data }) => data && setCategories(data.categories))
      .catch(() => {})
    return () => clearTimeout(first)
  }, [load])

  const save = async () => {
    if (!draft) return
    setError(null)
    const { id, ...body } = draft
    try {
      const result = id
        ? await api.PUT('/api/v1/staff/promotions/{promotion_id}', { params: { path: { promotion_id: id } }, body })
        : await api.POST('/api/v1/staff/promotions', { body })
      if (result.data) {
        setDraft(null)
        void load()
      } else setError(MESSAGES[result.error?.error.code ?? ''] ?? 'Проверьте поля акции.')
    } catch {
      setError('Не получилось связаться с сервером.')
    }
  }

  const remove = async (id: string) => {
    await api.DELETE('/api/v1/staff/promotions/{promotion_id}', { params: { path: { promotion_id: id } } })
    setDraft(null)
    void load()
  }

  const categoryName = (id: string | null | undefined) =>
    id ? (categories.find((c) => c.id === id)?.name ?? 'категория') : 'всё меню'

  if (draft) {
    return (
      <div className="editor-form">
        <h1 className="title staff-title">{draft.id ? 'Акция' : 'Новая акция'}</h1>
        <label className="field">
          <span>Текст для гостей</span>
          <input value={draft.title} maxLength={256} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
        </label>
        <label className="field">
          <span>Скидка, %</span>
          <input
            type="number"
            min={1}
            max={100}
            value={draft.percent}
            onChange={(e) => setDraft({ ...draft, percent: Number(e.target.value) })}
          />
        </label>
        <label className="field">
          <span>На что</span>
          <select
            value={draft.category_id ?? ''}
            onChange={(e) => setDraft({ ...draft, category_id: e.target.value || null })}
          >
            <option value="">Всё меню</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Начало (необязательно)</span>
          <input type="date" value={draft.starts_on ?? ''} onChange={(e) => setDraft({ ...draft, starts_on: e.target.value || null })} />
        </label>
        <label className="field">
          <span>Окончание (необязательно)</span>
          <input type="date" value={draft.ends_on ?? ''} onChange={(e) => setDraft({ ...draft, ends_on: e.target.value || null })} />
        </label>
        <label className="field">
          <span>Тип</span>
          <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as Draft['kind'] })}>
            <option value="auto">Автоматическая — цена сразу со скидкой</option>
            <option value="checked">С проверкой — гость отмечает, сотрудник подтверждает</option>
          </select>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={draft.enabled ?? true} onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })} />
          <span>Включена</span>
        </label>
        {error && <p className="error-text">{error}</p>}
        <div className="button-row">
          <button type="button" className="primary-button" onClick={() => void save()}>
            Сохранить
          </button>
          <button type="button" className="secondary-button" onClick={() => setDraft(null)}>
            Отмена
          </button>
          {draft.id && (
            <button type="button" className="secondary-button danger" onClick={() => void remove(draft.id!)}>
              Удалить
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <>
      <h1 className="title staff-title">Акции</h1>
      {error && <p className="error-text">{error}</p>}
      {!items && <div className="skeleton" style={{ height: 160, marginTop: 16 }} />}
      <ul className="list">
        {(items ?? []).map((item) => (
          <li key={item.id}>
            <button type="button" className="list-item" onClick={() => setDraft(item)}>
              <span>
                {item.title}
                <span className="caption muted">
                  {' '}
                  · {item.percent}% · {categoryName(item.category_id)} ·{' '}
                  {item.kind === 'checked' ? 'с проверкой' : 'автоматическая'}
                  {!item.enabled && ' · выключена'}
                </span>
              </span>
              <span aria-hidden="true">›</span>
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className="primary-button wide" onClick={() => setDraft({ ...EMPTY })}>
        Новая акция
      </button>
    </>
  )
}
