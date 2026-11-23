/** GET /job-offers/mine in demo mode: the offers you added plus the ones on your board. */
import type { MyOffer } from '@/api/jobOffers'

import { mockApplications } from './applications'
import { allMockOffers, toListItem } from './offers'

export const mockMyOffers = {
  list(): MyOffer[] {
    const apps = new Map(mockApplications.list().map((a) => [a.job_offer.id, a]))
    return allMockOffers()
      .filter((o) => o.is_private || apps.has(o.id))
      .map((o) => {
        const app = apps.get(o.id)
        return {
          ...toListItem(o),
          source: o.source,
          found_via: o.found_via,
          url: o.url,
          is_active: o.is_active,
          is_private: o.is_private,
          added_at: o.is_private || !app ? o.created_at : app.created_at,
          application: app ? { id: app.id, status: app.status, updated_at: app.updated_at } : null,
        }
      })
      .sort((a, b) => b.added_at.localeCompare(a.added_at) || b.id - a.id)
  },
}
