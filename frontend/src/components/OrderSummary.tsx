import type { Order } from '../api/types'
import { fmtDate, fmtDay, rub } from './ui'

export function QuoteBlock({ order }: { order: Order }) {
  const q = order.quote
  if (!q) return <p className="text-sm text-slate-500">Расчёт стоимости пока недоступен.</p>
  const rows: [string, string][] = [
    ['Материал', rub(q.cost_material)], ['Работа оборудования', rub(q.cost_machine)],
    ['Постобработка', rub(q.cost_post)], ['Доставка', rub(q.cost_delivery)],
  ]
  if (q.adjustment) rows.push(['Корректировка', rub(q.adjustment)])
  return (
    <div>
      <table className="w-full text-sm">
        <tbody>{rows.map(([k, v]) => <tr key={k}><td className="py-0.5 text-slate-500">{k}</td><td className="py-0.5 text-right">{v}</td></tr>)}</tbody>
      </table>
      <div className="mt-2 flex items-baseline justify-between border-t border-slate-200 pt-2 dark:border-slate-700">
        <span className="font-medium">Итого</span><span className="text-2xl font-bold">{rub(q.total)}</span>
      </div>
      <div className="mt-1 text-sm text-slate-500">Срок: {q.estimated_days} дн. · масса {q.mass_g.toFixed(1)} г · время печати {q.print_hours.toFixed(1)} ч</div>
    </div>
  )
}

export function ParamsBlock({ order }: { order: Order }) {
  const rows: [string, string][] = [
    ['Технология', order.technology?.code ?? '—'], ['Материал', order.material?.name ?? '—'],
    ['Качество', order.quality_profile?.name ?? '—'], ['Цвет', order.color?.name ?? '—'],
    ['Количество', String(order.quantity)],
    ['Постобработка', order.post_processing.map(p => p.name).join(', ') || 'нет'],
    ['Получение', order.delivery_method?.name ?? '—'],
  ]
  if (order.pickup_point) rows.push(['Пункт выдачи', order.pickup_point.name])
  if (order.delivery_address) rows.push(['Адрес доставки', order.delivery_address])
  if (order.planned_date) rows.push(['Плановая дата', fmtDay(order.planned_date)])
  if (order.assignment) {
    rows.push(['Принтер', `${order.assignment.printer} (${order.assignment.workshop})`])
    rows.push(['Окно печати', `${fmtDate(order.assignment.planned_start)} — ${fmtDate(order.assignment.planned_end)}`])
  }
  if (order.model) rows.push(['Модель', `${order.model.file_name} (${order.model.format}, ${(order.model.size_bytes / 1048576).toFixed(1)} МБ, v${order.model.version})`])
  if (order.model) rows.push(['Габариты, мм', order.model.bbox.map(x => x.toFixed(1)).join(' × ') + ` · ${order.model.volume_cm3.toFixed(1)} см³ · тел: ${order.model.body_count}`])
  return (
    <table className="w-full text-sm">
      <tbody>{rows.map(([k, v]) => <tr key={k}><td className="w-40 py-1 align-top text-slate-500">{k}</td><td className="py-1">{v}</td></tr>)}</tbody>
    </table>
  )
}
