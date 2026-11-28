import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, errMsg } from '../api/client'
import type { OrderList } from '../api/types'
import { ErrorBox, Spinner, StatusBadge, fmtDate, rub, STATUSES } from '../components/ui'

export default function MyOrders() {
  const [data, setData] = useState<OrderList | null>(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const nav = useNavigate()

  useEffect(() => {
    setData(null)
    api<OrderList>('/orders', { params: { status, page } }).then(setData).catch(e => setError(errMsg(e)))
  }, [status, page])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Мои заказы</h1>
        <div className="flex gap-2">
          <select className="input w-56" value={status} onChange={e => { setPage(1); setStatus(e.target.value) }}>
            <option value="">Все статусы</option>
            {STATUSES.map(s => <option key={s.code} value={s.code}>{s.label}</option>)}
          </select>
          <Link to="/orders/new" className="btn-primary">+ Новый заказ</Link>
        </div>
      </div>
      <ErrorBox message={error} />
      {!data ? <Spinner /> : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead className="border-b border-slate-200 dark:border-slate-800">
              <tr><th className="th">Номер</th><th className="th">Статус</th><th className="th">Материал</th><th className="th">Кол-во</th><th className="th">Стоимость</th><th className="th">Создан</th></tr>
            </thead>
            <tbody>
              {data.results.map(o => (
                <tr key={o.id} className="cursor-pointer border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50"
                  onClick={() => nav(o.status === 'DRAFT' ? '/orders/new?draft=' + o.id : '/orders/' + o.id)}>
                  <td className="td font-medium">{o.number}</td>
                  <td className="td"><StatusBadge status={o.status} /></td>
                  <td className="td">{o.material?.name ?? '—'}</td>
                  <td className="td">{o.quantity}</td>
                  <td className="td">{rub(o.total)}</td>
                  <td className="td">{fmtDate(o.created_at)}</td>
                </tr>
              ))}
              {data.results.length === 0 && <tr><td className="td text-center text-slate-500" colSpan={6}>Заказов пока нет. <Link className="text-indigo-600 underline" to="/orders/new">Создать первый заказ</Link></td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {data && data.count > data.page_size && (
        <div className="flex items-center justify-center gap-3">
          <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</button>
          <span className="text-sm">Стр. {page} из {Math.ceil(data.count / data.page_size)}</span>
          <button className="btn-secondary" disabled={page * data.page_size >= data.count} onClick={() => setPage(page + 1)}>Вперёд</button>
        </div>
      )}
    </div>
  )
}
