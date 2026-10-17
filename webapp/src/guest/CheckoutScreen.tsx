import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Checkout } from '../api/types'
import { platform } from '../platform'
import { useCart } from './cart'
import { formatPrice } from './format'
import { MainAction } from './MainAction'
import { NETWORK_ERROR, RETRY } from './texts'
import { useRemote } from './useRemote'

export type PaymentMethod = Checkout['payment_methods'][number]

export interface PlaceOrder {
  paymentMethod: PaymentMethod
  comment: string
}

interface Props {
  onBack: () => void
  /** Story 3.3: create the order; resolves to an error text or null. */
  onPlace?: (order: PlaceOrder) => Promise<string | null>
}

const loadCheckout = () => api.GET('/api/v1/checkout')

const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  online: 'Онлайн',
  cash: 'Наличными на кассе',
  card: 'Картой на кассе',
}

export function CheckoutScreen({ onBack, onPlace }: Props) {
  const { state, reload } = useRemote(loadCheckout)
  useEffect(() => platform.showBackButton(onBack), [onBack])
  return (
    <main className="screen checkout">
      {!platform.hasNativeBackButton && (
        <button type="button" className="text-button" onClick={onBack}>
          ← В корзину
        </button>
      )}
      <h1 className="title staff-title">Оформление</h1>
      {state.kind === 'loading' && <div className="skeleton" style={{ height: 260, marginTop: 16 }} />}
      {state.kind === 'error' && (
        <div className="notice">
          <p>{NETWORK_ERROR}</p>
          <button type="button" className="secondary-button" onClick={reload}>
            {RETRY}
          </button>
        </div>
      )}
      {state.kind === 'ready' && <CheckoutForm checkout={state.data} onPlace={onPlace} />}
    </main>
  )
}

function CheckoutForm({ checkout, onPlace }: { checkout: Checkout; onPlace?: Props['onPlace'] }) {
  const { cart } = useCart()
  const [name, setName] = useState(checkout.contact.first_name)
  const [phone, setPhone] = useState(checkout.contact.phone)
  const [typedPhone, setTypedPhone] = useState('')
  const [consent, setConsent] = useState(checkout.contact.has_consent)
  const [payment, setPayment] = useState<PaymentMethod>('online')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!checkout.is_open) {
    return (
      <div className="notice">
        <p>Сейчас мы закрыты. {checkout.status_text.replace('Закрыто, о', 'О')}.</p>
        <p className="muted">Меню можно посмотреть, а заказ — оформить, когда откроемся.</p>
      </div>
    )
  }

  const saveContact = async (body: { contact_raw?: string; phone?: string; first_name?: string; consent?: boolean }) => {
    const { data, error: failure } = await api.POST('/api/v1/me/contact', { body: { ...body, consent: body.consent ?? false } })
    if (data) {
      setPhone(data.phone)
      return null
    }
    return failure?.error.code === 'bad_phone' ? 'Проверьте номер телефона' : 'Не получилось сохранить контакт'
  }

  const share = async () => {
    setError(null)
    const raw = await platform.requestContact()
    if (raw) setError(await saveContact({ contact_raw: raw }))
    else setError('Не получилось получить контакт — введите номер вручную')
  }

  const ready = Boolean(phone || typedPhone.trim()) && consent && name.trim() && cart && cart.count > 0
  const place = async () => {
    if (!ready || !onPlace) return
    setBusy(true)
    setError(null)
    let failure = await saveContact({
      first_name: name,
      consent: true,
      ...(phone ? {} : { phone: typedPhone }),
    }).catch(() => NETWORK_ERROR)
    if (!failure) failure = await onPlace({ paymentMethod: payment, comment })
    setBusy(false)
    if (failure) setError(failure)
  }

  return (
    <div className="editor-form">
      <section className="card">
        <h2 className="section">Получение</h2>
        <p>Самовывоз · как можно скорее (≈{checkout.asap_minutes} мин)</p>
      </section>

      <section className="card">
        <h2 className="section">Контакты</h2>
        <label className="field">
          <span>Имя</span>
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="given-name" />
        </label>
        {phone ? (
          <p>
            Телефон: {phone}{' '}
            <button type="button" className="text-button" onClick={() => setPhone(null)}>
              Изменить
            </button>
          </p>
        ) : (
          <>
            <button type="button" className="secondary-button" onClick={share}>
              Поделиться контактом
            </button>
            <label className="field">
              <span>или введите номер</span>
              <input type="tel" value={typedPhone} onChange={(e) => setTypedPhone(e.target.value)} placeholder="+7 999 123-45-67" autoComplete="tel" />
            </label>
            {!typedPhone.trim() && <p className="caption muted">Нужен телефон, чтобы кафе могло связаться с вами.</p>}
          </>
        )}
        {!checkout.contact.has_consent && (
          <label className="toggle">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>Согласен(на) на обработку персональных данных для оформления заказа</span>
          </label>
        )}
        {!consent && <p className="caption muted">Без согласия мы не можем принять заказ.</p>}
      </section>

      <section className="card">
        <h2 className="section">Оплата</h2>
        {checkout.payment_methods.map((method) => (
          <label key={method} className="option">
            <input type="radio" name="payment" checked={payment === method} onChange={() => setPayment(method)} />
            <span className="option-name">{PAYMENT_LABELS[method]}</span>
          </label>
        ))}
      </section>

      <label className="field">
        <span>Комментарий к заказу</span>
        <textarea rows={2} value={comment} maxLength={500} onChange={(e) => setComment(e.target.value)} />
      </label>

      {error && <p className="error-text">{error}</p>}
      <MainAction
        text={`${payment === 'online' ? 'Оплатить' : 'Оформить'} · ${formatPrice(cart?.total ?? 0)}`}
        disabled={!ready || !onPlace}
        loading={busy}
        onClick={place}
      />
    </div>
  )
}
