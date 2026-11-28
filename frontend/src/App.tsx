import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import Register from './pages/Register'
import { PasswordReset, PasswordResetConfirm } from './pages/PasswordReset'
import NewOrder from './pages/NewOrder'
import MyOrders from './pages/MyOrders'
import OrderDetail from './pages/OrderDetail'
import Notifications from './pages/Notifications'
import ManagerPlaceholder from './pages/manager/ManagerPlaceholder'
import type { Role } from './api/types'

/**
 * ВРЕМЕННЫЙ ФРОНТЕНД КЛИЕНТСКОГО ПОРТАЛА (А. Г. Видерман).
 * Экраны входа/регистрации работают через временный адаптер `/api/auth/*`
 * до слияния модуля `users`. АРМ менеджера заменён заглушкой (зона ответственности А. Д. Колотухина).
 */
function Guard({ roles, children }: { roles?: Role[]; children: JSX.Element }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'CLIENT' ? '/orders' : '/manager'} replace />
}

const CLIENT: Role[] = ['CLIENT']
const STAFF: Role[] = ['MANAGER', 'ADMIN']

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<PasswordReset />} />
      <Route path="/reset-password/:uid/:token" element={<PasswordResetConfirm />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Home />} />
        <Route path="/orders" element={<Guard roles={CLIENT}><MyOrders /></Guard>} />
        <Route path="/orders/new" element={<Guard roles={CLIENT}><NewOrder /></Guard>} />
        <Route path="/orders/:id" element={<Guard roles={CLIENT}><OrderDetail /></Guard>} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/manager" element={<Guard roles={STAFF}><ManagerPlaceholder /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
