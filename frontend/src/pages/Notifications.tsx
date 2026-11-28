import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errMsg, notifyNotificationsChanged } from '../api/client'
import type { NotificationItem } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ErrorBox, Spinner, fmtDate } from '../components/ui'

export default function Notifications() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [items, setItems] = useState<NotificationItem[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () =>
    api<{ unread: number; results: NotificationItem[] }>('/notifications')
      .then(d => {
        setItems(d.results)
        notifyNotificationsChanged(d.unread)
      })
      .catch(e => setError(errMsg(e)))

  useEffect(() => { load() }, [])

  async function read(n: NotificationItem) {
    if (n.is_read) return
    try {
      await api(`/notifications/${n.id}/read`, { method: 'POST' })
      setItems(list => {
        if (!list) return list
        const next = list.map(x => x.id === n.id ? { ...x, is_read: true } : x)
        notifyNotificationsChanged(next.filter(x => !x.is_read).length)
        return next
      })
    } catch (e) {
      setError(errMsg(e))
    }
  }

  async function readAll() {
    if (!items || items.every(x => x.is_read)) return
    setBusy(true); setError('')
    try {
      await api('/notifications/read-all', { method: 'POST', body: {} })
      setItems(list => list && list.map(x => ({ ...x, is_read: true })))
      notifyNotificationsChanged(0)
    } catch (e) {
      setError(errMsg(e))
    } finally { setBusy(false) }
  }

  const isClient = user?.role === 'CLIENT'
  const href = (n: NotificationItem) => (isClient && n.order_id ? `/orders/${n.order_id}` : '/manager')
  const unreadCount = items ? items.filter(x => !x.is_read).length : 0

  async function openOrder(n: NotificationItem) {
    await read(n)
    nav(href(n))
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Центр уведомлений</h1>
        {unreadCount > 0 && (
          <button className="btn-secondary" disabled={busy} onClick={readAll}>
            Отметить все прочитанными ({unreadCount})
          </button>
        )}
      </div>
      <ErrorBox message={error} />
      {!items ? <Spinner /> : items.length === 0 ? <div className="card text-slate-500">Уведомлений пока нет.</div> : (
        <div className="space-y-2">
          {items.map(n => (
            <div key={n.id} className={`card flex items-center justify-between gap-4 ${n.is_read ? 'opacity-70' : 'border-indigo-400'}`}>
              <div>
                <div className="text-sm">{n.text}</div>
                <div className="mt-1 text-xs text-slate-500">{fmtDate(n.created_at)}</div>
              </div>
              <div className="flex shrink-0 gap-2">
                {n.order_id && (
                  <button className="btn-secondary" onClick={() => void openOrder(n)}>
                    {isClient ? 'Открыть заказ' : 'В АРМ менеджера'}
                  </button>
                )}
                {!n.is_read && <button className="btn-secondary" onClick={() => void read(n)}>Прочитано</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
