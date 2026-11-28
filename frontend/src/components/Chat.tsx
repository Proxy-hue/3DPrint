import { FormEvent, useEffect, useRef, useState } from 'react'
import { api, errMsg } from '../api/client'
import type { Message } from '../api/types'
import { ErrorBox, fmtDate } from './ui'

interface Props { orderId: string; allowUpload?: boolean; onChanged?: () => void }

/** Чат по заказу. Опрос раз в 15 секунд (WebSocket вне объёма). */
export default function Chat({ orderId, allowUpload, onChanged }: Props) {
  const [msgs, setMsgs] = useState<Message[]>([])
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loadError, setLoadError] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const load = (isCancelled?: () => boolean) =>
    api<Message[]>(`/orders/${orderId}/messages`)
      .then(d => {
        if (isCancelled?.()) return
        setMsgs(d)
        setLoadError('')
      })
      .catch(e => { if (!isCancelled?.()) setLoadError(errMsg(e)) })

  useEffect(() => {
    let stop = false
    const cancelled = () => stop
    void load(cancelled)
    const t = setInterval(() => void load(cancelled), 15000)
    return () => { stop = true; clearInterval(t) }
  }, [orderId])
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }) }, [msgs.length])

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!text.trim() && !file) return
    setBusy(true); setError('')
    try {
      if (file) {
        const fd = new FormData()
        fd.append('text', text)
        fd.append('file', file)
        await api(`/orders/${orderId}/messages`, { method: 'POST', form: fd })
      } else {
        await api(`/orders/${orderId}/messages`, { method: 'POST', body: { text } })
      }
      setText(''); setFile(null)
      if (fileInput.current) fileInput.current.value = ''
      await load()
      onChanged?.()
    } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }

  return (
    <div className="card">
      <h2 className="mb-3 text-lg font-semibold">Переписка по заказу</h2>
      <ErrorBox message={loadError} />
      <div ref={box} className="mb-3 mt-2 max-h-72 space-y-2 overflow-y-auto rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
        {msgs.length === 0 && <div className="text-sm text-slate-500">Сообщений пока нет.</div>}
        {msgs.map(m => (
          <div key={m.id} className="text-sm">
            <div className="text-xs text-slate-500">{m.author.full_name} · {fmtDate(m.created_at)}{m.model_version ? ` · модель v${m.model_version}` : ''}</div>
            <div className="whitespace-pre-wrap">{m.text}</div>
          </div>
        ))}
      </div>
      <ErrorBox message={error} />
      <form onSubmit={send} className="mt-2 space-y-2">
        <textarea className="input" rows={2} placeholder="Введите сообщение…" value={text} onChange={e => setText(e.target.value)} />
        <div className="flex flex-wrap items-center gap-3">
          {allowUpload && (
            <label className="text-sm">
              <span className="mr-2 text-slate-500">Новая версия модели:</span>
              <input ref={fileInput} type="file" accept=".stl,.obj,.3mf" onChange={e => setFile(e.target.files?.[0] ?? null)} />
            </label>
          )}
          <button className="btn-primary ml-auto" disabled={busy}>{busy ? 'Отправка…' : 'Отправить'}</button>
        </div>
      </form>
    </div>
  )
}
