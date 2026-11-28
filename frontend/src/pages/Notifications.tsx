import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errMsg } from '../api/client'
import type { NotificationItem } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ErrorBox, Spinner, fmtDate } from '../components/ui'

export default function Notifications() {
  const { user } = useAuth()
  const [items, setItems] = useState<NotificationItem[] | null>(null)
  const [error, setError] = useState('')
  const load = () => api<{ results: NotificationItem[] }>('/notifications').then(d => setItems(d.results)).catch(e => setError(errMsg(e)))
  useEffect(() => { load() }, [])
  async function read(n: NotificationItem) {
    if (n.is_read) return
    try { await api(`/notifications/${n.id}/read`, { method: 'POST' }); setItems(list => list && list.map(x => x.id === n.id ? { ...x, is_read: true } : x)) }
    catch (e) { setError(errMsg(e)) }
  }
  const href = (n: NotificationItem) => n.order_id ? (user?.role === 'CLIENT' ? `/orders/${n.order_id}` : `/manager/orders/${n.order_id}`) : '#'
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Центр уведомлений</h1>
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
                {n.order_id && <Link className="btn-secondary" to={href(n)} onClick={() => read(n)}>Открыть заказ</Link>}
                {!n.is_read && <button className="btn-secondary" onClick={() => read(n)}>Прочитано</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
