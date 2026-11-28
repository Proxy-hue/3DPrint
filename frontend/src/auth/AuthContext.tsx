import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react'
import { api, ensureCsrf } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (data: Record<string, unknown>) => Promise<User>
  logout: () => Promise<void>
}
const Ctx = createContext<AuthState>(null as unknown as AuthState)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    ;(async () => {
      try {
        await ensureCsrf()
        setUser(await api<User>('/auth/me'))
      } catch {
        setUser(null)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const u = await api<User>('/auth/login', { method: 'POST', body: { email, password } })
    await ensureCsrf()
    setUser(u)
    return u
  }, [])
  const register = useCallback(async (data: Record<string, unknown>) => {
    const u = await api<User>('/auth/register', { method: 'POST', body: data })
    await ensureCsrf()
    setUser(u)
    return u
  }, [])
  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }) } finally { setUser(null) }
    await ensureCsrf().catch(() => {})
  }, [])

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>
}
export const useAuth = () => useContext(Ctx)
