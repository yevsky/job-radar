import type {
  AdminOffer,
  AdminStats,
  AdminOfferPage,
  AdminOfferQuery,
  AdminUser,
  ImportReport,
  SearchLimitRead,
} from '@/api/admin'
import type { RoleName } from '@/api/auth'

import { ApiError } from '@/api/client'

import { mockAuth } from './auth'
import { daysFromNow, newId, notFound } from './util'

const DEFAULT_LIMIT = 10

let others: AdminUser[] = [
  {
    id: 2,
    email: 'marta@jobradar.local',
    role_id: 1,
    role: 'user',
    created_at: daysFromNow(-40),
    search_daily_limit: null,
  },
  {
    id: 3,
    email: 'piotr@jobradar.local',
    role_id: 1,
    role: 'user',
    created_at: daysFromNow(-12),
    search_daily_limit: 25,
  },
]
let ownLimit: number | null = null

const offer = (
  title: string,
  company_name: string,
  days: number,
  extra: Partial<AdminOffer> = {},
): AdminOffer => ({
  id: newId(),
  title,
  company_name,
  location: 'Wrocław',
  employment_type: 'full_time',
  experience_level: 'junior',
  deadline: null,
  technologies: ['Python'],
  source: 'manual',
  found_via: null,
  url: `https://jobs.example.com/${title.toLowerCase().replace(/\W+/g, '-')}`,
  is_active: true,
  last_seen_at: daysFromNow(days),
  created_at: daysFromNow(days),
  saved_by: 0,
  ...extra,
})

let offers: AdminOffer[] = [
  offer('Junior Python Developer', 'Northwind Analytics', -2, { saved_by: 3 }),
  offer('Backend Engineer', 'Lumen Health', -5, { location: 'Remote', saved_by: 1 }),
  offer('Data Engineer', 'Datafy', -9, { is_active: false, technologies: ['SQL', 'Airflow'] }),
  offer('React Developer', 'Pixel Forge', -14, { technologies: ['React', 'TypeScript'] }),
]

export const mockAdmin = {
  users(): AdminUser[] {
    return [{ ...mockAuth.me(), search_daily_limit: ownLimit }, ...others]
  },
  setLimit(userId: number, limit: number | null): SearchLimitRead {
    if (userId === mockAuth.me().id) ownLimit = limit
    else {
      const user = others.find((u) => u.id === userId) ?? notFound('User')
      user.search_daily_limit = limit
    }
    return { user_id: userId, search_daily_limit: limit, effective_limit: limit ?? DEFAULT_LIMIT }
  },
  setRole(userId: number, role: RoleName): AdminUser {
    if (userId === mockAuth.me().id) throw ownAccount()
    const user = others.find((u) => u.id === userId) ?? notFound('User')
    user.role = role
    user.role_id = role === 'admin' ? 2 : 1
    return user
  },
  stats(): AdminStats {
    const day = (n: number) => daysFromNow(n).slice(0, 10)
    const searches = [3, 5, 2, 0, 7, 9, 4, 6, 8, 1, 0, 5, 11, 6]
    const signups = [1, 0, 2, 1, 3, 1, 0, 2]
    return {
      users: others.length + 1,
      admins: 1 + others.filter((u) => u.role === 'admin').length,
      new_users_last_7_days: 1,
      public_offers: offers.filter((o) => o.is_active).length,
      hidden_offers: offers.filter((o) => !o.is_active).length,
      private_offers: 12,
      applications: 19,
      applications_by_status: {
        saved: 7,
        applied: 5,
        screening: 2,
        interview: 2,
        offer: 1,
        accepted: 0,
        rejected: 2,
        declined: 0,
      },
      searches_today: 6,
      searches_last_7_days: 37,
      analyses: 14,
      conversations: 5,
      searches_by_day: searches.map((count, i) => ({ day: day(i - 13), count })),
      signups_by_week: signups.map((count, i) => ({ day: day((i - 7) * 7), count })),
    }
  },
  async importFile(file: File): Promise<ImportReport> {
    const text = await file.text()
    const lines = text.split(/\r?\n/).filter((l) => l.trim())
    const rows = file.name.toLowerCase().endsWith('.csv')
      ? Math.max(lines.length - 1, 0)
      : (JSON.parse(text) as unknown[]).length
    for (let i = 0; i < rows; i++) offers.unshift(offer(`Imported offer ${i + 1}`, file.name, 0))
    return { created: rows, updated: 0, skipped: 0, errors: [] }
  },
  offers(query: AdminOfferQuery): AdminOfferPage {
    const q = (query.q ?? '').trim().toLowerCase()
    const found = offers.filter(
      (o) =>
        (!q || `${o.title} ${o.company_name}`.toLowerCase().includes(q)) &&
        (!query.source || o.source === query.source) &&
        (query.is_active == null || o.is_active === query.is_active),
    )
    const limit = query.limit ?? 25
    const offset = query.offset ?? 0
    return { items: found.slice(offset, offset + limit), total: found.length, limit, offset }
  },
  setOfferActive(offerId: number, isActive: boolean): AdminOffer {
    const found = offers.find((o) => o.id === offerId) ?? notFound('Job offer')
    found.is_active = isActive
    return found
  },
  deleteOffer(offerId: number): void {
    if (!offers.some((o) => o.id === offerId)) notFound('Job offer')
    offers = offers.filter((o) => o.id !== offerId)
  },
  deleteUser(userId: number): void {
    if (userId === mockAuth.me().id) throw ownAccount()
    if (!others.some((u) => u.id === userId)) notFound('User')
    others = others.filter((u) => u.id !== userId)
  },
}

function ownAccount() {
  return new ApiError(409, "You can't change your own role or delete your own account")
}
