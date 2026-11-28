export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'
const BASE: string = API_BASE

export function notifyNotificationsChanged(unread?: number) {
  window.dispatchEvent(new CustomEvent<{ unread?: number }>('notifications:changed', { detail: { unread } }))
}

export class ApiError extends Error {
  status: number
  code?: string
  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)
  return m ? decodeURIComponent(m[1]) : ''
}

interface Opts {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  form?: FormData
  params?: Record<string, string | number | undefined | null>
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const method = opts.method ?? 'GET'
  let url = BASE + path
  if (opts.params) {
    const q = new URLSearchParams()
    Object.entries(opts.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
    })
    const s = q.toString()
    if (s) url += (url.includes('?') ? '&' : '?') + s
  }
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (opts.form) {
    body = opts.form
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  if (method !== 'GET') headers['X-CSRFToken'] = csrfToken()
  let res: Response
  try {
    res = await fetch(url, {
      method,
      headers,
      body,
      credentials: 'include',
      cache: method === 'GET' ? 'no-store' : 'default',
    })
  } catch {
    throw new ApiError('Нет связи с сервером. Проверьте подключение.', 0)
  }
  const text = await res.text()
  let data: any = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!res.ok) {
    let msg: string = data?.detail || ''
    if (!msg && data && typeof data === 'object') {
      msg = Object.values(data).flat().join(' ')
    }
    if (res.status === 403 && /CSRF/i.test(msg)) msg = 'Сессия устарела. Обновите страницу и повторите действие.'
    if (!msg) msg = `Ошибка запроса (${res.status}).`
    throw new ApiError(msg, res.status, data?.code)
  }
  return data as T
}

export async function ensureCsrf() {
  await api('/auth/csrf')
}

export const errMsg = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка')
