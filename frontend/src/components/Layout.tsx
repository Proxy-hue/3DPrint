import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTheme } from './Theme'
import { api } from '../api/client'

function Bell({ userId }: { userId?: string }) {
  const [n, setN] = useState(0)
  const { pathname } = useLocation()
  const seq = useRef(0)

  useEffect(() => {
    if (!userId) return
    let stop = false
    const load = () => {
      const id = ++seq.current
      api<{ unread: number }>('/notifications')
        .then(d => { if (!stop && seq.current === id) setN(d.unread) })
        .catch(() => {})
    }
    const onChanged = (e: Event) => {
      const unread = (e as CustomEvent<{ unread?: number }>).detail?.unread
      if (typeof unread === 'number') {
        seq.current += 1
        setN(unread)
      } else {
        load()
      }
    }
    const onVisible = () => { if (document.visibilityState === 'visible') load() }
    load()
    const t = setInterval(load, 10000)
    window.addEventListener('notifications:changed', onChanged)
    window.addEventListener('focus', load)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      stop = true
      clearInterval(t)
      window.removeEventListener('notifications:changed', onChanged)
      window.removeEventListener('focus', load)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [userId, pathname])
  return (
    <Link to="/notifications" className="btn-secondary relative" title="Уведомления">
      🔔
      {n > 0 && <span className="absolute -right-1.5 -top-1.5 rounded-full bg-rose-600 px-1.5 text-xs text-white">{n}</span>}
    </Link>
  )
}

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800'}`

export default function Layout() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const nav = useNavigate()
  const manager = user?.role === 'MANAGER' || user?.role === 'ADMIN'
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3">
          <Link to="/" className="text-lg font-bold text-indigo-600 dark:text-indigo-400">3DPrint</Link>
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
            Временный клиентский UI
          </span>
          <nav className="flex gap-1">
            {manager ? (
              <NavLink to="/manager" end className={link}>АРМ менеджера</NavLink>
            ) : (
              <>
                <NavLink to="/orders/new" className={link}>Новый заказ</NavLink>
                <NavLink to="/orders" end className={link}>Мои заказы</NavLink>
              </>
            )}
            <NavLink to="/notifications" className={link}>Уведомления</NavLink>
            {user?.role === 'ADMIN' && <a href="/admin/" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800">Админ-панель</a>}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Bell userId={user?.id} />
            <button className="btn-secondary" onClick={toggle} title="Сменить тему">{theme === 'dark' ? '☀️ Светлая' : '🌙 Тёмная'}</button>
            <span className="hidden text-sm text-slate-500 lg:inline">{user?.full_name || user?.email}</span>
            <button className="btn-secondary" onClick={async () => { await logout(); nav('/login') }}>Выйти</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-6"><Outlet /></main>
    </div>
  )
}
