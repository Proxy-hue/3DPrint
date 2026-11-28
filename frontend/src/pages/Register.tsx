import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { errMsg } from '../api/client'
import { ErrorBox, Field } from '../components/ui'
import { AuthShell } from './Login'

export default function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ full_name: '', email: '', phone: '', password: '', client_type: 'INDIVIDUAL', company_name: '' })
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await register({ ...f, consent })
      nav('/orders', { replace: true })
    } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Регистрация клиента">
      <form onSubmit={submit} className="space-y-3">
        <ErrorBox message={error} />
        <Field label="ФИО"><input className="input" required value={f.full_name} onChange={set('full_name')} /></Field>
        <Field label="Электронная почта"><input className="input" type="email" required value={f.email} onChange={set('email')} /></Field>
        <Field label="Телефон"><input className="input" type="tel" value={f.phone} onChange={set('phone')} /></Field>
        <Field label="Тип клиента">
          <select className="input" value={f.client_type} onChange={set('client_type')}>
            <option value="INDIVIDUAL">Физическое лицо</option>
            <option value="COMPANY">Юридическое лицо</option>
          </select>
        </Field>
        {f.client_type === 'COMPANY' && <Field label="Название организации"><input className="input" required value={f.company_name} onChange={set('company_name')} /></Field>}
        <Field label="Пароль (не менее 8 символов)"><input className="input" type="password" required minLength={8} value={f.password} onChange={set('password')} /></Field>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={consent} onChange={e => setConsent(e.target.checked)} required />
          <span>Я даю согласие на обработку персональных данных</span>
        </label>
        <button className="btn-primary w-full" disabled={busy || !consent}>{busy ? 'Регистрация…' : 'Зарегистрироваться'}</button>
        <div className="text-center text-sm">Уже есть аккаунт? <Link className="text-indigo-600 hover:underline dark:text-indigo-400" to="/login">Войти</Link></div>
      </form>
    </AuthShell>
  )
}
