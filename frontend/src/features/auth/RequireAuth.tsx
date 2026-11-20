import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Loading } from '@/components/ui'

import { useAuth } from './AuthContext'

/** Route guard: logged-out users go to /login and come back afterwards. */
export function RequireAuth() {
  const { user, checking } = useAuth()
  const location = useLocation()
  if (checking) return <Loading label="Checking your session…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
