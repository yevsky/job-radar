/** Backend: routers/auth.py (exists). */
import { existing, request } from './client'
import { mockAuth } from '@/mocks/auth'

export type RoleName = 'user' | 'admin'

export interface UserRead {
  id: number
  email: string
  role_id: number
  /** 'admin' can open the admin pages. */
  role: RoleName
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

/** POST /auth/login takes an OAuth2 form: `username` is the email. */
export function login(email: string, password: string): Promise<Token> {
  const form = new URLSearchParams({ username: email, password })
  return existing(
    () => request<Token>('/auth/login', { method: 'POST', body: form }),
    () => mockAuth.login(email),
  )
}

export function register(email: string, password: string): Promise<UserRead> {
  return existing(
    () => request<UserRead>('/auth/register', { method: 'POST', body: { email, password } }),
    () => mockAuth.register(email),
  )
}

export function getMe(): Promise<UserRead> {
  return existing(
    () => request<UserRead>('/auth/me'),
    () => mockAuth.me(),
  )
}
