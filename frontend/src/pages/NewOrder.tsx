import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, errMsg, notifyNotificationsChanged } from '../api/client'
import type { Order } from '../api/types'
import ModelViewer from '../components/ModelViewerLazy'
import { QuoteBlock } from '../components/OrderSummary'
import { ErrorBox, Field, Spinner, VerdictPanel, rub } from '../components/ui'
import {
  type CatalogData,
  type CompatMatrix,
  type ColorItem,
  type DeliveryItem,
  type MaterialItem,
  type Paginated,
  type PickupItem,
  type PostProcItem,
  type QualityItem,
  type TechItem,
  fetchAllPages,
  filterColors,
  filterMaterials,
  filterQualities,
  postProcessingBlockReason,
} from '../utils/catalogCompat'

const STEPS = ['Модель', 'Параметры печати', 'Постобработка и получение', 'Расчёт и подтверждение']

const getCatPage = <T,>(path: string) => (page: number) =>
  api<T[] | Paginated<T>>(path, { params: page > 1 ? { page } : undefined })

async function loadCatalog(): Promise<CatalogData> {
  const [technologies, materials, quality, colors, pp, delivery, pickup, compat] = await Promise.all([
    fetchAllPages(getCatPage<TechItem>('/catalog/technologies/')),
    fetchAllPages(getCatPage<MaterialItem>('/catalog/materials/')),
    fetchAllPages(getCatPage<QualityItem>('/catalog/quality-profiles/')),
    fetchAllPages(getCatPage<ColorItem>('/catalog/colors/')),
    fetchAllPages(getCatPage<PostProcItem>('/catalog/post-processing/')),
    fetchAllPages(getCatPage<DeliveryItem>('/catalog/delivery-methods/')),
    fetchAllPages(getCatPage<PickupItem>('/catalog/pickup-points/')),
    api<CompatMatrix>('/catalog/compatibility/'),
  ])
  return { technologies, materials, quality, colors, pp, delivery, pickup, compat }
}

export default function NewOrder() {
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const [cat, setCat] = useState<CatalogData | null>(null)
  const [o, setO] = useState<Order | null>(null)
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [qty, setQty] = useState('1')
  const [address, setAddress] = useState('')
  const [comment, setComment] = useState('')
  const [desiredDate, setDesiredDate] = useState('')
  const [previewColor, setPreviewColor] = useState<ColorItem | null>(null)
  const orderRef = useRef<Order | null>(null)
  const patchQueueRef = useRef<Promise<Order | null>>(Promise.resolve(null))
  orderRef.current = o

  useEffect(() => { loadCatalog().then(setCat).catch(e => setError(errMsg(e))) }, [])
  useEffect(() => {
    const d = sp.get('draft')
    if (d) api<Order>(`/orders/${d}`).then(r => { orderRef.current = r; setO(r) }).catch(e => setError(errMsg(e)))
  }, [sp])
  useEffect(() => { if (o) setQty(String(o.quantity ?? 1)) }, [o?.id, o?.quantity])
  useEffect(() => { if (o) setAddress(o.delivery_address ?? '') }, [o?.id, o?.delivery_address])
  useEffect(() => { if (o) setComment(o.comment ?? '') }, [o?.id, o?.comment])
  useEffect(() => { if (o) setDesiredDate(o.desired_date ?? '') }, [o?.id, o?.desired_date])

  async function waitReady(id: string) {
    for (let i = 0; i < 40; i++) {
      const r = await api<Order>(`/orders/${id}`)
      if (r.ready) { orderRef.current = r; setO(r); return }
      await new Promise(res => setTimeout(res, 1000))
    }
    throw new Error('Проверка модели занимает слишком много времени. Обновите страницу.')
  }

  async function upload(file: File) {
    const ext = file.name.includes('.') ? file.name.split('.').pop()!.toUpperCase() : ''
    if (!['STL', 'OBJ', '3MF'].includes(ext)) {
      setError('E-01: Недопустимый формат файла. Поддерживаются только STL, OBJ, 3MF.')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('E-01: Размер файла превышает 50 МБ.')
      return
    }
    setBusy(true); setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (!o) {
        const created = await api<Order>('/orders', { method: 'POST', form: fd })
        orderRef.current = created
        setO(created)
        await waitReady(created.id)
      } else {
        await api(`/orders/${o.id}/model`, { method: 'POST', form: fd })
        await waitReady(o.id)
      }
    } catch (e) {
      setError(errMsg(e))
    } finally { setBusy(false) }
  }

  function patch(body: Record<string, unknown> | ((cur: Order) => Record<string, unknown>)): Promise<Order | null> {
    const run = patchQueueRef.current.then(async () => {
      const cur = orderRef.current
      if (!cur) return null
      const payload = typeof body === 'function' ? body(cur) : body
      setError('')
      try {
        const updated = await api<Order>(`/orders/${cur.id}`, {
          method: 'PATCH',
          body: { version: cur.version, ...payload },
        })
        orderRef.current = updated
        setO(updated)
        return updated
      } catch (e) {
        setError(errMsg(e))
        return null
      }
    })
    patchQueueRef.current = run.catch(() => null)
    return run
  }

  async function flushPending(): Promise<boolean> {
    setBusy(true)
    try {
      await patchQueueRef.current
      const cur = orderRef.current
      if (!cur) return true
      const pending: Record<string, unknown> = {}
      const parsedQty = Math.max(1, Number(qty) || 1)
      if (parsedQty !== cur.quantity) {
        setQty(String(parsedQty))
        pending.quantity = parsedQty
      }
      if (address !== cur.delivery_address) pending.delivery_address = address
      if (comment !== cur.comment) pending.comment = comment
      if (desiredDate !== (cur.desired_date ?? '')) {
        if (desiredDate && (!/^\d{4}-\d{2}-\d{2}$/.test(desiredDate) || desiredDate < todayStr)) {
          setError('Желаемая дата не может быть в прошлом.')
          return false
        }
        pending.desired_date = desiredDate || null
      }
      if (Object.keys(pending).length === 0) return true
      return (await patch(pending)) !== null
    } finally {
      setBusy(false)
    }
  }

  async function goNext() {
    if (!(await flushPending())) return
    setStep(step + 1)
  }

  async function confirmOrder() {
    if (!o) return
    if (!(await flushPending())) return
    setBusy(true); setError('')
    try {
      await api(`/orders/${o.id}/confirm`, { method: 'POST', body: {} })
      notifyNotificationsChanged()
      nav(`/orders/${o.id}`)
    }
    catch (e) { setError(errMsg(e)) } finally { setBusy(false) }
  }

  async function discard() {
    if (!o) return nav('/orders')
    if (!confirm('Удалить черновик?')) return
    await api(`/orders/${o.id}/cancel`, { method: 'POST', body: {} }).catch(() => {})
    notifyNotificationsChanged()
    nav('/orders')
  }

  if (!cat) return error ? <ErrorBox message={error} /> : <Spinner />

  const techId = o?.technology?.id
  const materials = filterMaterials(cat, techId)
  const mat = materials.find(m => m.id === o?.material?.id)
  const colors = filterColors(cat, mat)
  const qualities = filterQualities(cat, techId)
  const fmt3mfMulti = o?.model?.format === '3MF' && (o?.model?.body_count ?? 1) > 1
  const ppSel = o?.post_processing.map(p => p.id) ?? []
  const dm = cat.delivery.find(d => d.id === o?.delivery_method?.id)
  const todayStr = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Moscow' }).format(new Date())

  const canNext = [
    !!o?.model && !!o?.ready,
    !!(o?.technology && o?.material && o?.quality_profile && o?.color),
    !!dm && (dm.type === 'PICKUP' ? !!o?.pickup_point : address.trim().length > 3),
    true,
  ][step]

  const activeColor = previewColor ?? (colors.find(c => c.id === o?.color?.id) ?? (
    o?.color ? { id: o.color.id, name: o.color.name, hex: o.color.hex ?? '', is_transparent: !!o.color.is_transparent } : null
  ))
  const swatchBg = (c: { hex: string; is_transparent: boolean }) =>
    c.is_transparent && !c.hex ? 'linear-gradient(135deg, #e2e8f0 0%, #93c5fd 100%)' : c.hex

  const validPpFor = (cur: Order, nextTechId?: string, nextColorId?: string) => {
    const curPp = cur.post_processing.map(p => p.id)
    if (!cat) return curPp
    const curMulti = cur.model?.format === '3MF' && (cur.model?.body_count ?? 1) > 1
    return curPp.filter(id => {
      const p = cat.pp.find(item => item.id === id)
      return p
        ? postProcessingBlockReason(p, cat, { techId: nextTechId, colorId: nextColorId, isMultibody3mf: curMulti }) === null
        : false
    })
  }

  function pickTech(id: string) {
    setPreviewColor(null)
    void patch({ technology: id, material: null, quality_profile: null, color: null, post_processing: [] })
  }

  function pickMaterial(materialId: string) {
    setPreviewColor(null)
    void patch(cur => {
      const curPp = cur.post_processing.map(p => p.id)
      const validPp = validPpFor(cur, cur.technology?.id, undefined)
      const body: Record<string, unknown> = { material: materialId, color: null }
      if (validPp.length !== curPp.length) body.post_processing = validPp
      return body
    })
  }

  async function pickColor(c: ColorItem) {
    setPreviewColor(c)
    await patch(cur => {
      const curPp = cur.post_processing.map(p => p.id)
      const validPp = validPpFor(cur, cur.technology?.id, c.id)
      const body: Record<string, unknown> = { color: c.id }
      if (validPp.length !== curPp.length) body.post_processing = validPp
      return body
    })
    setPreviewColor(cur => (cur?.id === c.id ? null : cur))
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Новый заказ {o ? `· ${o.number}` : ''}</h1>
        <button className="btn-secondary" onClick={discard}>Отменить</button>
      </div>
      <ol className="flex gap-2">
        {STEPS.map((s, i) => (
          <li key={s} className={`flex-1 rounded-lg border px-3 py-2 text-sm ${i === step ? 'border-indigo-500 bg-indigo-600 text-white' : i < step ? 'border-emerald-400 text-emerald-700 dark:text-emerald-300' : 'border-slate-200 text-slate-400 dark:border-slate-800'}`}>
            {i + 1}. {s}
          </li>
        ))}
      </ol>
      <ErrorBox message={error} />

      <div className="grid gap-4 lg:grid-cols-5">
        <div className={`space-y-4 ${!(o?.model || o?.quote) ? 'lg:col-span-5' : 'lg:col-span-3'}`}>
          {step === 0 && (
            <div className="card space-y-3">
              <h2 className="text-lg font-semibold">Загрузка 3D-модели</h2>
              <p className="text-sm text-slate-500">Форматы STL, OBJ, 3MF (единицы измерения — миллиметры, мм), размер до 50 МБ. Один заказ — один файл (несколько деталей — в одном 3MF).</p>
              <input type="file" accept=".stl,.obj,.3mf" disabled={busy} onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = '' }} />
              {busy && <p className="text-sm text-slate-500">Загрузка и проверка модели…</p>}
              {o?.model && (
                <ModelViewer
                  orderId={o.id}
                  version={o.model.version}
                  format={o.model.format}
                  colorHex={activeColor?.hex}
                  transparent={activeColor?.is_transparent}
                  height={380}
                />
              )}
              {o?.model && <p className="text-sm text-slate-500">{o.model.file_name} · {o.model.bbox.map(x => x.toFixed(1)).join(' × ')} мм · {o.model.volume_cm3.toFixed(1)} см³ · тел: {o.model.body_count}</p>}
            </div>
          )}

          {step === 1 && o && (
            <div className="card space-y-4">
              <h2 className="text-lg font-semibold">Параметры печати</h2>
              <Field label="Технология">
                <select className="input" value={techId ?? ''} onChange={e => pickTech(e.target.value)}>
                  <option value="" disabled>Выберите технологию</option>
                  {cat.technologies.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </Field>
              <Field label="Материал">
                <select className="input" disabled={!techId} value={o.material?.id ?? ''} onChange={e => pickMaterial(e.target.value)}>
                  <option value="" disabled>{techId ? 'Выберите материал' : 'Сначала выберите технологию'}</option>
                  {materials.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </Field>
              <Field label="Качество печати">
                <select className="input" disabled={!techId} value={o.quality_profile?.id ?? ''} onChange={e => patch({ quality_profile: e.target.value })}>
                  <option value="" disabled>Выберите качество</option>
                  {qualities.map(q => <option key={q.id} value={q.id}>{q.name} ({q.layer_height_mm} мм)</option>)}
                </select>
              </Field>
              <Field label="Цвет">
                <div className="flex flex-wrap gap-2">
                  {!mat && <span className="text-sm text-slate-500">Сначала выберите материал</span>}
                  {colors.map(c => (
                    <button key={c.id} type="button" onClick={() => void pickColor(c)}
                      className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${activeColor?.id === c.id ? 'border-indigo-500 ring-2 ring-indigo-400' : 'border-slate-300 dark:border-slate-700'}`}>
                      <span className="h-4 w-4 rounded-full border border-slate-400" style={{ background: swatchBg(c) }} />{c.name}
                    </button>
                  ))}
                </div>
              </Field>
              <Field label="Количество копий">
                <input
                  className="input w-32"
                  type="number"
                  min={1}
                  value={qty}
                  onChange={e => setQty(e.target.value)}
                  onBlur={() => {
                    const n = Math.max(1, Number(qty) || 1)
                    setQty(String(n))
                    if (n !== o.quantity) void patch({ quantity: n })
                  }}
                />
              </Field>
            </div>
          )}

          {step === 2 && o && (
            <div className="space-y-4">
              <div className="card space-y-2">
                <h2 className="text-lg font-semibold">Постобработка</h2>
                {cat.pp.map(p => {
                  const reason = postProcessingBlockReason(p, cat, { techId, colorId: o.color?.id, isMultibody3mf: fmt3mfMulti })
                  const blocked = reason !== null
                  return (
                    <label key={p.id} className={`flex items-center gap-3 rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-800 ${blocked ? 'opacity-50' : ''}`}>
                      <input type="checkbox" disabled={blocked || busy} checked={ppSel.includes(p.id)}
                        onChange={e => {
                          const checked = e.target.checked
                          void patch(cur => {
                            const curPp = cur.post_processing.map(item => item.id)
                            return {
                              post_processing: checked
                                ? Array.from(new Set([...curPp, p.id]))
                                : curPp.filter(x => x !== p.id),
                            }
                          })
                        }} />
                      <span className="flex-1">{p.name}{blocked && <em className="ml-2 text-xs text-rose-600">{reason}</em>}</span>
                      <span>{rub(p.price)} · {p.hours} ч</span>
                    </label>
                  )
                })}
              </div>
              <div className="card space-y-3">
                <h2 className="text-lg font-semibold">Получение</h2>
                {cat.delivery.map(d => (
                  <label key={d.id} className="flex items-center gap-3 text-sm">
                    <input
                      type="radio"
                      name="delivery"
                      checked={o.delivery_method?.id === d.id}
                      onChange={() => {
                        const body: Record<string, unknown> = { delivery_method: d.id, pickup_point: null }
                        if (d.type !== 'COURIER') {
                          setAddress('')
                          body.delivery_address = ''
                        }
                        void patch(body)
                      }}
                    />
                    {d.name} — {Number(d.price) ? rub(d.price) : 'бесплатно'}, {d.days} дн.
                  </label>
                ))}
                {dm?.type === 'PICKUP' && (
                  <Field label="Пункт выдачи">
                    <select className="input" value={o.pickup_point?.id ?? ''} onChange={e => patch({ pickup_point: e.target.value })}>
                      <option value="" disabled>Выберите пункт</option>
                      {cat.pickup.filter(p => p.delivery_method === dm.id).map(p => <option key={p.id} value={p.id}>{p.name} — {p.address}</option>)}
                    </select>
                  </Field>
                )}
                {dm?.type === 'COURIER' && (
                  <Field label="Адрес доставки">
                    <input
                      className="input"
                      value={address}
                      onChange={e => setAddress(e.target.value)}
                    />
                  </Field>
                )}
                <Field label="Желаемая дата выполнения (необязательно)">
                  <input
                    className="input w-56"
                    type="date"
                    min={todayStr}
                    value={desiredDate}
                    onChange={e => {
                      const val = e.target.value
                      setDesiredDate(val)
                      if (!val || (/^\d{4}-\d{2}-\d{2}$/.test(val) && val >= todayStr)) {
                        void patch({ desired_date: val || null })
                      }
                    }}
                  />
                </Field>
                <Field label="Комментарий к заказу">
                  <textarea
                    className="input"
                    rows={2}
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                  />
                </Field>
              </div>
            </div>
          )}

          {step === 3 && o && (
            <div className="card space-y-3">
              <h2 className="text-lg font-semibold">Расчёт и подтверждение</h2>
              <QuoteBlock order={o} />
              <VerdictPanel v={o.validation} />
              {o.validation?.verdict === 'ERROR' && <p className="text-sm text-amber-600">Заказ можно отправить — менеджер проверит его вручную.</p>}
              <button className="btn-primary w-full" disabled={busy || !o.model} onClick={confirmOrder}>Подтвердить заказ</button>
            </div>
          )}
        </div>

        {(o?.model || o?.quote) && (
          <aside className="space-y-4 lg:col-span-2">
            {step > 0 && o?.model && (
              <div className="card space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold">3D-превью модели</h3>
                  {activeColor && (
                    <span className="flex items-center gap-1.5 text-xs text-slate-500">
                      <span className="h-3 w-3 rounded-full border border-slate-400" style={{ background: swatchBg(activeColor) }} />
                      {activeColor.name}
                    </span>
                  )}
                </div>
                <ModelViewer
                  orderId={o.id}
                  version={o.model.version}
                  format={o.model.format}
                  colorHex={activeColor?.hex}
                  transparent={activeColor?.is_transparent}
                  height={250}
                />
              </div>
            )}
            {step > 0 && step < 3 && o?.quote && (
              <div className="card">
                <h3 className="mb-2 font-semibold">Предварительный расчёт</h3>
                <QuoteBlock order={o} />
              </div>
            )}
            {step < 3 && o?.model && (
              <div className="card">
                <h3 className="mb-2 font-semibold">Проверка модели</h3>
                <VerdictPanel v={o.validation ?? null} />
              </div>
            )}
          </aside>
        )}
      </div>

      <div className="flex justify-between">
        <button className="btn-secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>Назад</button>
        {step < 3 && <button className="btn-primary" disabled={!canNext || busy} onClick={goNext}>Далее</button>}
      </div>
    </div>
  )
}
