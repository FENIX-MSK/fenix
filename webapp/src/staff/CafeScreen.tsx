import { useRef, useState } from 'react'

import { api } from '../api/client'
import type { LocationInfo } from '../api/types'
import { useLocationInfo } from '../guest/useLocationInfo'
import { MAX_PHOTO_BYTES, PHOTO_MESSAGES, uploadPhoto } from './photoUpload'

const WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

const MESSAGES: Record<string, string> = {
  bad_time: 'Время в формате ЧЧ:ММ',
  contacts_required: 'Укажите адрес и телефон',
  bad_coordinates: 'Координаты: обе или никаких',
  bad_social_link: 'Ссылки — с https:// и названием',
}

interface DayDraft {
  open: boolean
  opens: string
  closes: string
}

const pad = (time: string) => time.padStart(5, '0')

export function CafeScreen() {
  const { state, reload } = useLocationInfo()
  if (state.kind === 'loading') return <div className="skeleton" style={{ height: 320, marginTop: 16 }} />
  if (state.kind === 'error') return <p className="error-text">Не получилось загрузить данные кафе.</p>
  return <CafeForm key={JSON.stringify(state.data.opening_hours)} info={state.data} onSaved={reload} />
}

function CafeForm({ info, onSaved }: { info: LocationInfo; onSaved: () => void }) {
  const coordinates = new URL(info.map_url).searchParams.get('pt')?.split(',')
  const [address, setAddress] = useState(info.address)
  const [lat, setLat] = useState(coordinates?.[1] ?? '')
  const [lon, setLon] = useState(coordinates?.[0] ?? '')
  const [phone, setPhone] = useState(info.phone)
  const [description, setDescription] = useState(info.description)
  const [links, setLinks] = useState(info.social_links.map((l) => ({ ...l })))
  const byDay = new Map(info.opening_hours.map((h) => [h.weekday, h]))
  const [days, setDays] = useState<DayDraft[]>(
    WEEKDAYS.map((_, weekday) => {
      const hours = byDay.get(weekday)
      return { open: Boolean(hours), opens: pad(hours?.opens_at ?? '9:00'), closes: pad(hours?.closes_at ?? '22:00') }
    }),
  )
  const [photos, setPhotos] = useState(info.photos)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const file = useRef<HTMLInputElement>(null)

  const save = async () => {
    setBusy(true)
    setMessage(null)
    let code: string | null = 'network'
    try {
      const { error } = await api.PUT('/api/v1/staff/location', {
        body: {
          address,
          phone,
          description,
          latitude: lat ? Number(lat.replace(',', '.')) : null,
          longitude: lon ? Number(lon.replace(',', '.')) : null,
          social_links: links,
          opening_hours: days.flatMap((d, weekday) => (d.open ? [{ weekday, opens_at: d.opens, closes_at: d.closes }] : [])),
        },
      })
      code = error ? error.error.code : null
    } catch {
      // network: keep the form
    }
    setBusy(false)
    if (code === null) {
      setMessage({ ok: true, text: 'Сохранено — гости уже видят изменения' })
      onSaved()
    } else setMessage({ ok: false, text: MESSAGES[code] ?? 'Не сохранилось, попробуйте ещё раз' })
  }

  const addPhoto = async (picked: File) => {
    if (picked.size > MAX_PHOTO_BYTES) return setMessage({ ok: false, text: PHOTO_MESSAGES.image_too_large })
    try {
      const body = (await uploadPhoto('/api/v1/staff/location/photos', picked, () => {})) as { photos: string[] }
      setPhotos(body.photos)
    } catch (error) {
      const code = error instanceof Error ? error.message : ''
      setMessage({ ok: false, text: PHOTO_MESSAGES[code] ?? 'Не удалось загрузить фото' })
    }
  }

  const removePhoto = async (url: string) => {
    const { data } = await api.DELETE('/api/v1/staff/location/photos', { params: { query: { key: url } } }).catch(() => ({ data: undefined }))
    if (data) setPhotos(data.photos)
  }

  const setDay = (index: number, patch: Partial<DayDraft>) => setDays(days.map((d, i) => (i === index ? { ...d, ...patch } : d)))

  return (
    <form
      className="editor-form"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      <h1 className="title staff-title">Кафе</h1>

      <fieldset className="choice-group">
        <legend className="choice-legend">Часы работы</legend>
        <p className="caption muted">Закрытие раньше открытия — работа после полуночи.</p>
        {WEEKDAYS.map((name, index) => (
          <div className="hours-edit" key={name}>
            <label className="toggle">
              <input type="checkbox" checked={days[index].open} onChange={(e) => setDay(index, { open: e.target.checked })} />
              <span>{name}</span>
            </label>
            {days[index].open ? (
              <span className="hours-inputs">
                <input type="time" aria-label={`${name}: открытие`} value={days[index].opens} onChange={(e) => setDay(index, { opens: e.target.value })} />
                –
                <input type="time" aria-label={`${name}: закрытие`} value={days[index].closes} onChange={(e) => setDay(index, { closes: e.target.value })} />
              </span>
            ) : (
              <span className="muted">Выходной</span>
            )}
          </div>
        ))}
      </fieldset>

      <label className="field">
        <span>Адрес</span>
        <input value={address} onChange={(e) => setAddress(e.target.value)} required />
      </label>
      <div className="size-row two">
        <label className="field">
          <span>Широта (для карты)</span>
          <input inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="55.75" />
        </label>
        <label className="field">
          <span>Долгота</span>
          <input inputMode="decimal" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="37.61" />
        </label>
      </div>
      <label className="field">
        <span>Телефон</span>
        <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required />
      </label>
      <label className="field">
        <span>Описание</span>
        <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>

      <fieldset className="choice-group">
        <legend className="choice-legend">Соцсети</legend>
        {links.map((link, index) => (
          <div className="size-row" key={index}>
            <input aria-label="Название" value={link.title} onChange={(e) => setLinks(links.map((l, i) => (i === index ? { ...l, title: e.target.value } : l)))} />
            <input aria-label="Ссылка" value={link.url} onChange={(e) => setLinks(links.map((l, i) => (i === index ? { ...l, url: e.target.value } : l)))} placeholder="https://" />
            <span />
            <button type="button" className="icon-button" aria-label="Удалить ссылку" onClick={() => setLinks(links.filter((_, i) => i !== index))}>
              ✕
            </button>
          </div>
        ))}
        <button type="button" className="text-button" onClick={() => setLinks([...links, { kind: 'link', title: '', url: 'https://' }])}>
          + Ссылка
        </button>
      </fieldset>

      <fieldset className="choice-group">
        <legend className="choice-legend">Фото кафе</legend>
        <div className="photo-strip">
          {photos.map((url) => (
            <div key={url} className="photo-thumb">
              <img src={url} alt="Фото кафе" />
              <button type="button" className="icon-button" aria-label="Убрать фото" onClick={() => removePhoto(url)}>
                ✕
              </button>
            </div>
          ))}
        </div>
        <input
          ref={file}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
          onChange={(e) => {
            const picked = e.target.files?.[0]
            e.target.value = ''
            if (picked) void addPhoto(picked)
          }}
        />
        <button type="button" className="text-button" onClick={() => file.current?.click()}>
          + Фото
        </button>
      </fieldset>

      {message && <p className={message.ok ? 'muted' : 'error-text'}>{message.text}</p>}
      <button type="submit" className="primary-button" disabled={busy}>
        Сохранить
      </button>
    </form>
  )
}
