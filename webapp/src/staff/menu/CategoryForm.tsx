import { useState } from 'react'

import { api } from '../../api/client'
import type { StaffCategory } from '../../api/types'
import { attempt } from './saveError'

interface Props {
  category: StaffCategory | null
  onDone: () => void
}

export function CategoryForm({ category, onDone }: Props) {
  const [name, setName] = useState(category?.name ?? '')
  const [description, setDescription] = useState(category?.description ?? '')
  const [hidden, setHidden] = useState(category?.is_hidden ?? false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const save = async () => {
    setBusy(true)
    const body = { name, description, is_hidden: hidden }
    const failure = await attempt(() =>
      category
        ? api.PUT('/api/v1/staff/categories/{category_id}', { params: { path: { category_id: category.id } }, body })
        : api.POST('/api/v1/staff/categories', { body }),
    )
    setBusy(false)
    if (failure) setError(failure)
    else onDone()
  }

  const remove = async () => {
    if (!category) return
    if (!confirmDelete) return setConfirmDelete(true)
    const failure = await attempt(() =>
      api.DELETE('/api/v1/staff/categories/{category_id}', { params: { path: { category_id: category.id } } }),
    )
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
      <h2 className="title staff-title">{category ? 'Категория' : 'Новая категория'}</h2>
      <label className="field">
        <span>Название</span>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={128} required />
      </label>
      <label className="field">
        <span>Подпись</span>
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="например, 32 см" />
      </label>
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
        {category && (
          <button type="button" className="text-button danger-text" onClick={remove}>
            {confirmDelete ? 'Точно удалить?' : 'Удалить'}
          </button>
        )}
      </div>
    </form>
  )
}
