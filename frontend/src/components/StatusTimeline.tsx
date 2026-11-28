import type { Order } from '../api/types'
import { STATUSES, fmtDate } from './ui'

/** Временная шкала из 14 статусов: пройденные подсвечены, текущий выделен. */
export default function StatusTimeline({ order }: { order: Order }) {
  const visited = new Map<string, string>()
  visited.set('DRAFT', order.created_at)
  order.events.forEach(e => { if (e.to_status) visited.set(e.to_status, e.created_at) })
  return (
    <div className="card">
      <h2 className="mb-3 text-lg font-semibold">Статусы заказа</h2>
      <ol className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
        {STATUSES.map(s => {
          const cur = s.code === order.status
          const was = visited.has(s.code)
          const cls = cur ? 'border-indigo-500 bg-indigo-600 text-white'
            : was ? 'border-emerald-400 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200'
              : 'border-slate-200 text-slate-400 dark:border-slate-800'
          return (
            <li key={s.code} className={`rounded-lg border px-2 py-1.5 text-xs ${cls}`}>
              <div className="font-medium">{s.label}</div>
              <div className="opacity-70">{was ? fmtDate(visited.get(s.code)) : '—'}</div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
