import { FormEvent, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, errMsg } from '../api/client'
import { ErrorBox, Field, InfoBox } from '../components/ui'
import { AuthShell } from './Login'

export function PasswordReset() {
  const [email, setEmail] = useState('')
  const [done, setDone] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try { setDone((await api<{ detail: string }>('/auth/password-reset', { method: 'POST', body: { email } })).detail) }
    catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Восстановление пароля">
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        {done && <InfoBox>{done}</InfoBox>}
        <Field label="Электронная почта"><input className="input" type="email" required value={email} onChange={e => setEmail(e.target.value)} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Отправка…' : 'Отправить ссылку'}</button>
        <div className="text-center text-sm"><Link className="text-indigo-600 hover:underline dark:text-indigo-400" to="/login">Вернуться ко входу</Link></div>
      </form>
    </AuthShell>
  )
}

export function PasswordResetConfirm() {
  const { uid, token } = useParams()
  const nav = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      setDone((await api<{ detail: string }>('/auth/password-reset/confirm', { method: 'POST', body: { uid, token, password } })).detail)
      setTimeout(() => nav('/login'), 1500)
    } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Новый пароль">
      <form onSubmit={submit} className="space-y-4">
        <ErrorBox message={error} />
        {done && <InfoBox>{done}</InfoBox>}
        <Field label="Новый пароль"><input className="input" type="password" required minLength={8} value={password} onChange={e => setPassword(e.target.value)} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Сохранение…' : 'Сохранить пароль'}</button>
      </form>
    </AuthShell>
  )
}
