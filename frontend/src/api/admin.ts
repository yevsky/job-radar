/**
 * Backend: routers/admin.py (exists, admin role only).
 *   GET /admin/users                           -> AdminUser[]
 *   PUT /admin/users/{id}/search-limit {search_daily_limit: int | null} -> SearchLimitRead
 * `search_daily_limit` on the user list is optional: shown once the backend adds it.
 */
import type { UserRead } from './auth'
import { existing, request } from './client'
import { mockAdmin } from '@/mocks/admin'

export interface AdminUser extends UserRead {
  /** The user's own daily search limit; null = the default from settings. */
  search_daily_limit?: number | null
}

export interface SearchLimitRead {
  user_id: number
  search_daily_limit: number | null
  effective_limit: number
}

export const listUsers = () =>
  existing(
    () => request<AdminUser[]>('/admin/users'),
    () => mockAdmin.users(),
  )

/** `null` puts the user back on the default limit. */
export const setSearchLimit = (userId: number, limit: number | null) =>
  existing(
    () =>
      request<SearchLimitRead>(`/admin/users/${userId}/search-limit`, {
        method: 'PUT',
        body: { search_daily_limit: limit },
      }),
    () => mockAdmin.setLimit(userId, limit),
  )
