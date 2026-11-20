/**
 * Saved offers are applications with status `saved` (backend milestone 9). The /saved-jobs
 * endpoints are a shortcut over them, so this mock reads the demo applications.
 */
import type { SavedJob } from '@/api/savedJobs'
import type { Application } from '@/api/applications'
import type { JobOfferListItem } from '@/api/jobOffers'

import { mockApplications } from './applications'

const toSaved = (a: Application): SavedJob => ({
  id: a.id,
  job_offer: a.job_offer,
  created_at: a.created_at,
})

const savedRows = () => mockApplications.list().filter((a) => a.status === 'saved')

export const mockSaved = {
  list: () =>
    savedRows()
      .map(toSaved)
      .sort((a, b) => b.created_at.localeCompare(a.created_at)),
  add(offer: JobOfferListItem): SavedJob {
    const existing = mockApplications.forOffer(offer.id)
    if (existing) return toSaved(existing)
    return toSaved(mockApplications.create({ job_offer_id: offer.id, status: 'saved' }, offer))
  },
  remove(offerId: number): void {
    const row = savedRows().find((a) => a.job_offer.id === offerId)
    if (row) mockApplications.remove(row.id)
  },
}
