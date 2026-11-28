import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

type Theme = 'light' | 'dark'
const Ctx = createContext<{ theme: Theme; toggle: () => void }>({ theme: 'dark', toggle: () => {} })

function initial(): Theme {
  try {
    const s = localStorage.getItem('theme')
    if (s === 'light' || s === 'dark') return s
  } catch { /* недоступно */ }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initial)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try { localStorage.setItem('theme', theme) } catch { /* ignore */ }
  }, [theme])
  return <Ctx.Provider value={{ theme, toggle: () => setTheme(t => (t === 'dark' ? 'light' : 'dark')) }}>{children}</Ctx.Provider>
}
export const useTheme = () => useContext(Ctx)
