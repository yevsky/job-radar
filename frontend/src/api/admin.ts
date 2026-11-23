/**
 * Backend: routers/admin.py (exists, admin role only).
 *   GET /admin/users                           -> AdminUser[]
 *   PUT /admin/users/{id}/search-limit {search_daily_limit: int | null} -> SearchLimitRead
 *   PATCH /admin/users/{id}/role {role}          -> AdminUser
 *   DELETE /admin/users/{id}                      -> 204
 *   POST /admin/job-offers/import (file: JSON or CSV) -> ImportReport
 *   GET /admin/job-offers ?q&source&is_active&limit&offset -> AdminOfferPage
 *   PATCH /admin/job-offers/{id} {is_active} / DELETE /admin/job-offers/{id}
 */
import type { RoleName, UserRead } from './auth'
import { existing, request } from './client'
import type { SourceKind } from './enums'
import type { JobOfferListItem } from './jobOffers'
import { mockAdmin } from '@/mocks/admin'

export interface AdminUser extends UserRead {
  /** The user's own daily search limit; null = the default from settings. */
  search_daily_limit: number | null
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

/** Not for your own account: the backend answers 409. */
export const setRole = (userId: number, role: RoleName) =>
  existing(
    () => request<AdminUser>(`/admin/users/${userId}/role`, { method: 'PATCH', body: { role } }),
    () => mockAdmin.setRole(userId, role),
  )

/** Deletes the account with its profile, private offers, applications, CVs and chats. */
export const deleteUser = (userId: number) =>
  existing(
    () => request<void>(`/admin/users/${userId}`, { method: 'DELETE' }),
    () => mockAdmin.deleteUser(userId),
  )

export interface ImportRowError {
  /** 1-based: the offer's place in the JSON list, or its line after the CSV header. */
  row: number
  message: string
}

export interface ImportReport {
  created: number
  updated: number
  skipped: number
  errors: ImportRowError[]
}

export const importOffers = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return existing(
    () => request<ImportReport>('/admin/job-offers/import', { method: 'POST', body: form }),
    () => mockAdmin.importFile(file),
  )
}

export interface AdminOffer extends JobOfferListItem {
  source: SourceKind
  found_via: string | null
  url: string
  is_active: boolean
  last_seen_at: string | null
  created_at: string
  /** How many users track it (saved or applied). */
  saved_by: number
}

export interface AdminOfferPage {
  items: AdminOffer[]
  total: number
  limit: number
  offset: number
}

export interface AdminOfferQuery {
  q?: string
  source?: SourceKind | ''
  is_active?: boolean | null
  limit?: number
  offset?: number
}

export const listImportedOffers = (query: AdminOfferQuery) =>
  existing(
    () => request<AdminOfferPage>('/admin/job-offers', { query: { ...query } }),
    () => mockAdmin.offers(query),
  )

/** Hide an offer from everyone's list (false) or show it again (true). */
export const setOfferActive = (offerId: number, isActive: boolean) =>
  existing(
    () =>
      request<unknown>(`/admin/job-offers/${offerId}`, {
        method: 'PATCH',
        body: { is_active: isActive },
      }),
    () => mockAdmin.setOfferActive(offerId, isActive),
  )

export const deleteOffer = (offerId: number) =>
  existing(
    () => request<void>(`/admin/job-offers/${offerId}`, { method: 'DELETE' }),
    () => mockAdmin.deleteOffer(offerId),
  )
