import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { SalesReport } from '../api/types'
import { formatPrice } from '../guest/format'

type Period = 'day' | 'week' | 'month' | 'custom'

const PERIODS: { id: Period; label: string }[] = [
  { id: 'day', label: 'Сегодня' },
  { id: 'week', label: 'Неделя' },
  { id: 'month', label: 'Месяц' },
  { id: 'custom', label: 'Период' },
]

const PAYMENT: Record<string, string> = { online: 'Онлайн', cash: 'Наличные', card: 'Карта' }
const FULFILMENT: Record<string, string> = { pickup: 'Самовывоз', delivery: 'Доставка' }
const day = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })

/** «Отчёты» (FR-36): revenue counts handed over and delivered orders only. */
export function ReportsScreen() {
  const [period, setPeriod] = useState<Period>('day')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [report, setReport] = useState<SalesReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (period === 'custom' && (!start || !end)) return
    setError(null)
    try {
      const query = period === 'custom' ? { period, start, end } : { period }
      const { data, error: failure } = await api.GET('/api/v1/staff/reports/sales', { params: { query } })
      if (data) setReport(data)
      else setError(failure?.error.code === 'bad_period' ? 'Проверьте даты периода.' : 'Не получилось загрузить отчёт.')
    } catch {
      setError('Не получилось связаться с сервером.')
    }
  }, [period, start, end])

  useEffect(() => {
    const first = setTimeout(() => void load(), 0)
    return () => clearTimeout(first)
  }, [load])

  return (
    <>
      <h1 className="title staff-title">Отчёты</h1>
      <div className="chips">
        {PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={period === item.id ? 'chip active' : 'chip'}
            aria-pressed={period === item.id}
            onClick={() => setPeriod(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {period === 'custom' && (
        <div className="address-fields">
          <label className="field">
            <span>С</span>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="field">
            <span>По</span>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
      {!report && !error && <div className="skeleton" style={{ height: 200, marginTop: 16 }} />}
      {report && (
        <>
          <p className="muted">
            {report.start === report.end
              ? day.format(new Date(report.start))
              : `${day.format(new Date(report.start))} — ${day.format(new Date(report.end))}`}
          </p>
          <div className="report-kpis">
            <div className="card">
              <p className="caption muted">Выручка</p>
              <p className="report-big">{formatPrice(report.revenue)}</p>
            </div>
            <div className="card">
              <p className="caption muted">Заказов выдано</p>
              <p className="report-big">
                {report.completed} <span className="caption muted">из {report.orders}</span>
              </p>
            </div>
            <div className="card">
              <p className="caption muted">Средний чек</p>
              <p className="report-big">{formatPrice(report.average_check)}</p>
            </div>
          </div>
          <Breakdown title="Оплата" rows={Object.entries(report.by_payment).map(([k, v]) => [PAYMENT[k] ?? k, formatPrice(v)])} />
          <Breakdown title="Получение" rows={Object.entries(report.by_fulfilment).map(([k, v]) => [FULFILMENT[k] ?? k, String(v)])} />
          <Breakdown
            title="Топ блюд"
            rows={report.top_dishes.map((d) => [d.title, `${d.quantity} шт · ${formatPrice(d.revenue)}`])}
          />
          <Breakdown
            title={`Отмены · ${report.cancelled}`}
            rows={Object.entries(report.cancel_reasons).map(([k, v]) => [k, String(v)])}
          />
          <Breakdown
            title="Новые гости по источникам"
            rows={Object.entries(report.new_guests).map(([k, v]) => [k === 'direct' ? 'без метки' : k, String(v)])}
          />
        </>
      )}
    </>
  )
}

function Breakdown({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <section className="card">
      <h2 className="section">{title}</h2>
      {rows.length === 0 ? (
        <p className="muted">Нет данных</p>
      ) : (
        <ul className="order-lines">
          {rows.map(([name, value]) => (
            <li key={name} className="order-line">
              <span>{name}</span>
              <span className="price">{value}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
