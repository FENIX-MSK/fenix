import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { OrderParams } from '../api/types'

const STEPS = [5, 10, 15, 20, 30, 60]

type NumberField = Exclude<keyof OrderParams, 'delivery_enabled'>

const FIELDS: { key: NumberField; label: string; rubles?: boolean }[] = [
  { key: 'prep_minutes', label: 'Время приготовления, мин' },
  { key: 'unpaid_timeout_minutes', label: 'Ожидание онлайн-оплаты, мин' },
  { key: 'delivery_fee', label: 'Стоимость доставки, ₽', rubles: true },
  { key: 'load_moderate_from', label: '«Умеренно» — заказов в работе от' },
  { key: 'load_busy_from', label: '«Загружено» — заказов в работе от' },
  { key: 'load_moderate_extra', label: 'Добавка к ожиданию при «умеренно», мин' },
  { key: 'load_busy_extra', label: 'Добавка к ожиданию при «загружено», мин' },
]

/** Pauses and order parameters (FR-30, FR-31, FR-37). */
export function OrderSettingsScreen() {
  const [params, setParams] = useState<OrderParams | null>(null)
  const [pauses, setPauses] = useState<{ orders_paused?: boolean | null; delivery_paused?: boolean | null } | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .GET('/api/v1/staff/location/order-params')
      .then(({ data }) => data && setParams(data))
      .catch(() => setMessage({ ok: false, text: 'Не получилось загрузить параметры.' }))
    api
      .GET('/api/v1/staff/location/pauses')
      .then(({ data }) => data && setPauses(data))
      .catch(() => {})
  }, [])

  const togglePause = async (key: 'orders_paused' | 'delivery_paused', value: boolean) => {
    const before = pauses
    setPauses({ ...pauses, [key]: value })
    try {
      const { data } = await api.PUT('/api/v1/staff/location/pauses', { body: { [key]: value } })
      if (data) return setPauses(data)
    } catch {
      // below
    }
    setPauses(before)
    setMessage({ ok: false, text: 'Не сохранилось, попробуйте ещё раз.' })
  }

  const save = async () => {
    if (!params) return
    setBusy(true)
    setMessage(null)
    try {
      const { data, error } = await api.PUT('/api/v1/staff/location/order-params', { body: params })
      if (data) setMessage({ ok: true, text: 'Сохранено. Действует для новых заказов.' })
      else
        setMessage({
          ok: false,
          text: error?.error.code === 'bad_params' ? 'Проверьте значения: пороги и добавки по возрастанию.' : 'Не сохранилось.',
        })
    } catch {
      setMessage({ ok: false, text: 'Не получилось связаться с сервером.' })
    }
    setBusy(false)
  }

  return (
    <div className="editor-form">
      <h1 className="title staff-title">Приём и параметры заказа</h1>
      {pauses && (
        <section className="card">
          <label className="toggle">
            <input
              type="checkbox"
              checked={Boolean(pauses.orders_paused)}
              onChange={(e) => void togglePause('orders_paused', e.target.checked)}
            />
            <span>Приём заказов приостановлен</span>
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={Boolean(pauses.delivery_paused)}
              onChange={(e) => void togglePause('delivery_paused', e.target.checked)}
            />
            <span>Доставка приостановлена</span>
          </label>
          <p className="caption muted">Уже принятые заказы это не затрагивает.</p>
        </section>
      )}
      {!params && !message && <div className="skeleton" style={{ height: 240, marginTop: 16 }} />}
      {params && (
        <section className="card">
          <label className="toggle">
            <input
              type="checkbox"
              checked={params.delivery_enabled}
              onChange={(e) => setParams({ ...params, delivery_enabled: e.target.checked })}
            />
            <span>Доставка по ЖК</span>
          </label>
          <label className="field">
            <span>Шаг слотов предзаказа, мин</span>
            <select
              value={params.slot_step_minutes}
              onChange={(e) => setParams({ ...params, slot_step_minutes: Number(e.target.value) })}
            >
              {STEPS.map((step) => (
                <option key={step} value={step}>
                  {step}
                </option>
              ))}
            </select>
          </label>
          {FIELDS.map((field) => (
            <label key={field.key} className="field">
              <span>{field.label}</span>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                value={field.rubles ? params[field.key] / 100 : params[field.key]}
                onChange={(e) => {
                  const value = Math.round(Number(e.target.value) || 0)
                  setParams({ ...params, [field.key]: field.rubles ? value * 100 : value })
                }}
              />
            </label>
          ))}
          <button type="button" className="primary-button wide" disabled={busy} onClick={() => void save()}>
            Сохранить
          </button>
        </section>
      )}
      {message && <p className={message.ok ? 'muted' : 'error-text'}>{message.text}</p>}
    </div>
  )
}
