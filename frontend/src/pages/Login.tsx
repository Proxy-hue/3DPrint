import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { errMsg } from '../api/client'
import { ErrorBox, Field } from '../components/ui'

export function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="card w-full max-w-md">
        <div className="mb-1 text-2xl font-bold text-indigo-600 dark:text-indigo-400">3DPrint</div>
        <h1 className="mb-4 text-lg font-semibold">{title}</h1>
        {children}
      </div>
    </div>
  )
}

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const u = await login(email, password)
      nav(u.role === 'CLIENT' ? '/orders' : '/manager', { replace: true })
    } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Вход в личный кабинет">
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        <Field label="Электронная почта"><input className="input" type="email" required autoFocus value={email} onChange={e => setEmail(e.target.value)} /></Field>
        <Field label="Пароль"><input className="input" type="password" required value={password} onChange={e => setPassword(e.target.value)} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Вход…' : 'Войти'}</button>
        <div className="flex justify-between text-sm">
          <Link className="text-indigo-600 hover:underline dark:text-indigo-400" to="/register">Регистрация</Link>
          <Link className="text-indigo-600 hover:underline dark:text-indigo-400" to="/forgot-password">Забыли пароль?</Link>
        </div>
      </form>
    </AuthShell>
  )
}
