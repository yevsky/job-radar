import type { AdminUser, SearchLimitRead } from '@/api/admin'

import { mockAuth } from './auth'
import { daysFromNow, notFound } from './util'

const DEFAULT_LIMIT = 10

const others: AdminUser[] = [
  {
    id: 2,
    email: 'marta@jobradar.local',
    role_id: 1,
    created_at: daysFromNow(-40),
    search_daily_limit: null,
  },
  {
    id: 3,
    email: 'piotr@jobradar.local',
    role_id: 1,
    created_at: daysFromNow(-12),
    search_daily_limit: 25,
  },
]
let ownLimit: number | null = null

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
}
