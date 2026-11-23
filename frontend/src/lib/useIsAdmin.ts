import { useAuth } from '@/features/auth/AuthContext'

/** True when the logged-in user has the admin role (GET /auth/me says `role: 'admin'`). */
export function useIsAdmin(): boolean {
  const { user } = useAuth()
  return user?.role === 'admin'
}
