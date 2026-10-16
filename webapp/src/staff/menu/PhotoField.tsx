import { useEffect, useRef, useState } from 'react'

import { api } from '../../api/client'
import { MAX_PHOTO_BYTES, PHOTO_MESSAGES, uploadPhoto } from '../photoUpload'

type Upload = { kind: 'idle' } | { kind: 'uploading'; progress: number; preview: string } | { kind: 'failed'; file: File; message: string }

interface Props {
  dishId: string
  photoUrl: string | null
  onChanged: (photoUrl: string | null) => void
}

export function PhotoField({ dishId, photoUrl, onChanged }: Props) {
  const [upload, setUpload] = useState<Upload>({ kind: 'idle' })
  const input = useRef<HTMLInputElement>(null)

  useEffect(
    () => () => {
      if (upload.kind === 'uploading') URL.revokeObjectURL(upload.preview)
    },
    [upload],
  )

  const send = async (file: File) => {
    if (file.size > MAX_PHOTO_BYTES) return setUpload({ kind: 'failed', file, message: PHOTO_MESSAGES.image_too_large })
    const preview = URL.createObjectURL(file)
    setUpload({ kind: 'uploading', progress: 0, preview })
    try {
      const body = (await uploadPhoto(`/api/v1/staff/dishes/${dishId}/photo`, file, (progress) =>
        setUpload({ kind: 'uploading', progress, preview }),
      )) as { photo_url: string }
      const url = body.photo_url
      setUpload({ kind: 'idle' })
      onChanged(url)
    } catch (error) {
      // The old photo stays until a new one is stored.
      const code = error instanceof Error ? error.message : ''
      setUpload({ kind: 'failed', file, message: PHOTO_MESSAGES[code] ?? 'Не удалось загрузить фото' })
    }
  }

  const remove = async () => {
    const { error } = await api
      .DELETE('/api/v1/staff/dishes/{dish_id}/photo', { params: { path: { dish_id: dishId } } })
      .catch(() => ({ error: true }))
    if (!error) onChanged(null)
  }

  const shown = upload.kind === 'uploading' ? upload.preview : photoUrl
  return (
    <div className="photo-field">
      <div className="photo-preview">
        {shown ? <img src={shown} alt="Фото блюда" /> : <span className="caption muted">Нет фото</span>}
        {upload.kind === 'uploading' && (
          <div className="photo-progress" role="progressbar" aria-valuenow={Math.round(upload.progress * 100)}>
            <span style={{ width: `${upload.progress * 100}%` }} />
          </div>
        )}
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) void send(file)
        }}
      />
      <div className="button-row">
        <button type="button" className="secondary-button" disabled={upload.kind === 'uploading'} onClick={() => input.current?.click()}>
          {photoUrl ? 'Заменить фото' : 'Добавить фото'}
        </button>
        {photoUrl && upload.kind !== 'uploading' && (
          <button type="button" className="text-button danger-text" onClick={remove}>
            Убрать фото
          </button>
        )}
      </div>
      {upload.kind === 'failed' && (
        <p className="error-text">
          {upload.message}{' '}
          <button type="button" className="text-button" onClick={() => void send(upload.file)}>
            Повторить
          </button>
        </p>
      )}
    </div>
  )
}
