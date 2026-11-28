import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { API_BASE, api, errMsg, notifyNotificationsChanged } from '../api/client'
import type { Order } from '../api/types'
import Chat from '../components/Chat'
import ModelViewer from '../components/ModelViewerLazy'
import { ParamsBlock, QuoteBlock } from '../components/OrderSummary'
import StatusTimeline from '../components/StatusTimeline'
import { ErrorBox, InfoBox, Spinner, StatusBadge, VerdictPanel, fmtDate, eventLabel } from '../components/ui'

export default function OrderDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [o, setO] = useState<Order | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback((isCancelled?: () => boolean) =>
    api<Order>(`/orders/${id}`)
      .then(d => { if (!isCancelled?.()) { setO(d); setError('') } })
      .catch(e => { if (!isCancelled?.()) setError(errMsg(e)) }), [id])
  useEffect(() => {
    let stop = false
    const cancelled = () => stop
    void load(cancelled)
    const t = setInterval(() => void load(cancelled), 15000)
    return () => { stop = true; clearInterval(t) }
  }, [load])

  async function act(path: string, body?: unknown, after?: (r: Order) => void) {
    setBusy(true); setError('')
    try {
      const r = await api<Order>(`/orders/${id}/${path}`, { method: 'POST', body: body ?? {} })
      setO(r)
      notifyNotificationsChanged()
      after?.(r)
    } catch (e) { setError(errMsg(e)) } finally { setBusy(false) }
  }

  if (!o) return error ? <ErrorBox message={error} /> : <Spinner />
  const cancellable = ['NEW', 'CHECKED', 'MANUAL_REVIEW', 'CLARIFICATION', 'AWAITING_PAYMENT'].includes(o.status)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Заказ {o.number}</h1>
        <StatusBadge status={o.status} />
        <span className="text-sm text-slate-500">создан {fmtDate(o.created_at)}</span>
        <div className="ml-auto flex gap-2">
          <button className="btn-secondary" disabled={busy} onClick={() => act('repeat', {}, r => nav(`/orders/new?draft=${r.id}`))}>Повторить заказ</button>
          {o.status === 'AWAITING_PAYMENT' && <button className="btn-primary" disabled={busy} onClick={() => act('pay')}>Оплатить (заглушка)</button>}
          {cancellable && <button className="btn-danger" disabled={busy} onClick={() => confirm('Отменить заказ?') && act('cancel')}>Отменить заказ</button>}
        </div>
      </div>
      <ErrorBox message={error} />
      {o.status === 'AWAITING_PAYMENT' && <InfoBox>Оплата в учебной версии имитируется — нажмите «Оплатить (заглушка)» для перехода в статус «Оплачен».</InfoBox>}
      {o.status === 'CLARIFICATION' && <InfoBox>Менеджер запросил уточнение. Ответьте в переписке ниже или загрузите исправленную модель — заказ вернётся на проверку.</InfoBox>}
      {o.reject_reason && <ErrorBox message={`Причина: ${o.reject_reason}`} />}
      <StatusTimeline order={o} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          {o.model && (
            <div className="space-y-2">
              <ModelViewer
                orderId={o.id}
                version={o.model.version}
                format={o.model.format}
                colorHex={o.color?.hex}
                transparent={o.color?.is_transparent}
              />
              <a className="btn-secondary inline-flex" href={`${API_BASE.replace(/\/$/, '')}/orders/${o.id}/model/${o.model.version}/download`}>
                Скачать модель ({o.model.file_name})
              </a>
            </div>
          )}
          <div className="card"><h2 className="mb-2 text-lg font-semibold">Проверка модели</h2><VerdictPanel v={o.validation} /></div>
        </div>
        <div className="space-y-4">
          <div className="card"><h2 className="mb-2 text-lg font-semibold">Параметры</h2><ParamsBlock order={o} /></div>
          <div className="card"><h2 className="mb-2 text-lg font-semibold">Стоимость и срок</h2><QuoteBlock order={o} /></div>
        </div>
      </div>
      <Chat
        orderId={o.id}
        allowUpload={o.status === 'CLARIFICATION' || o.status === 'MANUAL_REVIEW'}
        onChanged={() => { void load(); notifyNotificationsChanged() }}
      />
      <div className="card">
        <h2 className="mb-2 text-lg font-semibold">История</h2>
        <ul className="space-y-1 text-sm">
          {[...o.events].reverse().map(e => (
            <li key={e.id}><span className="text-slate-500">{fmtDate(e.created_at)}</span> — {e.actor}: {eventLabel(e)}{e.reason ? ` (${e.reason})` : ''}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
