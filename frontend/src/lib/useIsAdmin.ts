import { listUsers } from '@/api/admin'
import { useAuth } from '@/features/auth/AuthContext'

import { useAsync } from './useAsync'

/**
 * True when the backend lets this user into /admin (it answers 403 otherwise).
 * Asking the backend avoids hard-coding which role_id is the admin one.
 */
export function useIsAdmin(): boolean {
  const { user } = useAuth()
  const check = useAsync(
    () =>
      user
        ? listUsers().then(
            () => true,
            () => false,
          )
        : Promise.resolve(false),
    [user?.id],
  )
  return check.data ?? false
}
