import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import * as authApi from '@/api/auth'
import { refreshAccessToken, setUnauthorizedHandler, tokenStore } from '@/api/client'

interface AuthState {
  user: authApi.UserRead | null
  /** True until we know whether the stored token or the refresh cookie still works. */
  checking: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  /** Ends the login on the backend too, so the refresh cookie stops working. */
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<authApi.UserRead | null>(null)
  const [checking, setChecking] = useState(true)

  /** Forget the login in this tab only (the backend already said it ended). */
  const forget = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Logged out here anyway; the cookie expires on its own
    }
    forget()
  }, [forget])

  useEffect(() => {
    setUnauthorizedHandler(forget)
    // No access token (a new tab, or it was cleared): the refresh cookie may still log us in
    const ready = tokenStore.get() ? Promise.resolve(true) : refreshAccessToken().then(Boolean)
    ready
      .then(async (loggedIn) => {
        if (loggedIn) setUser(await authApi.getMe())
      })
      .catch(forget)
      .finally(() => setChecking(false))
    return () => setUnauthorizedHandler(null)
  }, [forget])

  const login = useCallback(async (email: string, password: string) => {
    const token = await authApi.login(email, password)
    tokenStore.set(token.access_token)
    setUser(await authApi.getMe())
  }, [])

  const register = useCallback(
    async (email: string, password: string) => {
      await authApi.register(email, password)
      await login(email, password)
    },
    [login],
  )

  const value = useMemo(
    () => ({ user, checking, login, register, logout }),
    [user, checking, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
