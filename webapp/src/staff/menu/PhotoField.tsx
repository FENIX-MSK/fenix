import { useEffect, useRef, useState } from 'react'

import { api } from '../../api/client'
import { platform } from '../../platform'

const MAX_BYTES = 15 * 1024 * 1024

type Upload = { kind: 'idle' } | { kind: 'uploading'; progress: number; preview: string } | { kind: 'failed'; file: File; message: string }

interface Props {
  dishId: string
  photoUrl: string | null
  onChanged: (photoUrl: string | null) => void
}

/** XHR rather than fetch: upload progress (EXPERIENCE.md › «Загрузка фото»). */
function uploadPhoto(dishId: string, file: File, onProgress: (share: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `/api/v1/staff/dishes/${dishId}/photo`)
    const initData = platform.getInitDataRaw()
    if (initData) request.setRequestHeader('Authorization', `tma ${initData}`)
    request.upload.onprogress = (event) => event.lengthComputable && onProgress(event.loaded / event.total)
    request.onload = () => {
      const body = JSON.parse(request.responseText || 'null')
      if (request.status === 200) resolve(body.photo_url)
      else reject(new Error(body?.error?.code ?? 'failed'))
    }
    request.onerror = () => reject(new Error('network'))
    const form = new FormData()
    form.append('file', file)
    request.send(form)
  })
}

const MESSAGES: Record<string, string> = {
  unsupported_image: 'Нужна фотография JPEG, PNG, WebP или HEIC',
  image_too_large: 'Фото больше 15 МБ',
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
    if (file.size > MAX_BYTES) return setUpload({ kind: 'failed', file, message: MESSAGES.image_too_large })
    const preview = URL.createObjectURL(file)
    setUpload({ kind: 'uploading', progress: 0, preview })
    try {
      const url = await uploadPhoto(dishId, file, (progress) => setUpload({ kind: 'uploading', progress, preview }))
      setUpload({ kind: 'idle' })
      onChanged(url)
    } catch (error) {
      // The old photo stays until a new one is stored.
      const code = error instanceof Error ? error.message : ''
      setUpload({ kind: 'failed', file, message: MESSAGES[code] ?? 'Не удалось загрузить фото' })
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
