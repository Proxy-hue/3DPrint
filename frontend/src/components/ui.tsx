import { ReactNode } from 'react'

export const STATUSES: { code: string; label: string }[] = [
  { code: 'DRAFT', label: 'Черновик' },
  { code: 'NEW', label: 'Новый' },
  { code: 'CHECKED', label: 'Проверен' },
  { code: 'MANUAL_REVIEW', label: 'Ручная проверка' },
  { code: 'CLARIFICATION', label: 'Требуется уточнение' },
  { code: 'AWAITING_PAYMENT', label: 'Ожидает оплаты' },
  { code: 'PAID', label: 'Оплачен' },
  { code: 'DISTRIBUTED', label: 'Распределён' },
  { code: 'PRINTING', label: 'В печати' },
  { code: 'POST_PROCESSING', label: 'Постобработка' },
  { code: 'READY', label: 'Готов к выдаче' },
  { code: 'COMPLETED', label: 'Выполнен' },
  { code: 'REJECTED', label: 'Отклонён' },
  { code: 'CANCELLED', label: 'Отменён' },
]
export const statusLabel = (c: string) => STATUSES.find(s => s.code === c)?.label ?? c

export const EVENT_LABELS: Record<string, string> = {
  CREATED: 'Создание черновика',
  STATUS_CHANGED: 'Смена статуса',
  MESSAGE: 'Сообщение в переписке',
  ASSIGNED: 'Назначение принтера',
  PRICE_ADJUSTED: 'Корректировка стоимости',
  PRIORITY_CHANGED: 'Изменение приоритета',
  REPEATED: 'Повтор заказа',
}
export const eventLabel = (e: { type: string; from_status?: string | null; to_status?: string | null }) => {
  if (e.type === 'STATUS_CHANGED') {
    const frm = e.from_status ? `${statusLabel(e.from_status)} → ` : ''
    return `Статус: ${frm}«${statusLabel(e.to_status || '')}»`
  }
  return EVENT_LABELS[e.type] ?? e.type
}

const TONE: Record<string, string> = {
  DRAFT: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  NEW: 'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200',
  CHECKED: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
  MANUAL_REVIEW: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
  CLARIFICATION: 'bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-200',
  REJECTED: 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200',
  CANCELLED: 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200',
  COMPLETED: 'bg-teal-100 text-teal-800 dark:bg-teal-900/50 dark:text-teal-200',
}
export function StatusBadge({ status }: { status: string }) {
  const cls = TONE[status] ?? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-200'
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{statusLabel(status)}</span>
}

export const rub = (n: number | string | null | undefined) =>
  n === null || n === undefined || n === '' ? '—' : new Intl.NumberFormat('ru-RU').format(Math.round(Number(n))) + ' ₽'
export const fmtDate = (s?: string | null) =>
  s ? new Date(s).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '—'
export const fmtDay = (s?: string | null) => (s ? new Date(s).toLocaleDateString('ru-RU') : '—')

export function ErrorBox({ message }: { message?: string }) {
  if (!message) return null
  return <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-800 dark:bg-rose-950/50 dark:text-rose-200">{message}</div>
}
export function InfoBox({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-2 text-sm text-sky-800 dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-200">{children}</div>
}
export function Spinner({ text = 'Загрузка…' }: { text?: string }) {
  return <div className="py-10 text-center text-sm text-slate-500">{text}</div>
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="label">{label}</span>{children}</label>
}

export function VerdictPanel({ v }: { v: { verdict: string; issues: { code: string; message: string }[] } | null }) {
  if (!v) return <p className="text-sm text-slate-500">Проверка модели выполняется…</p>
  const tone = v.verdict === 'ERROR' ? 'border-rose-400 bg-rose-50 dark:bg-rose-950/40'
    : v.verdict === 'WARNING' ? 'border-amber-400 bg-amber-50 dark:bg-amber-950/40'
      : 'border-emerald-400 bg-emerald-50 dark:bg-emerald-950/40'
  const title = v.verdict === 'ERROR' ? 'Обнаружены ошибки — заказ уйдёт на ручную проверку менеджером'
    : v.verdict === 'WARNING' ? 'Есть предупреждения' : 'Замечаний нет'
  return (
    <div className={`rounded-lg border p-3 ${tone}`}>
      <div className="mb-1 text-sm font-semibold">{title}</div>
      <ul className="space-y-1 text-sm">
        {v.issues.map((i, k) => (
          <li key={k}><span className="mr-2 rounded bg-black/10 px-1.5 py-0.5 font-mono text-xs dark:bg-white/10">{i.code}</span>{i.message}</li>
        ))}
      </ul>
    </div>
  )
}
