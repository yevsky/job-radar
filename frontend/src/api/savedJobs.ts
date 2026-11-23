/**
 * Saved offers. Milestone 9: planned. A saved offer is an application with status `saved`;
 * these endpoints are a shortcut over the applications table.
 *
 * Planned contract:
 *   GET    /saved-jobs                 -> SavedJob[] (newest first)
 *   POST   /saved-jobs {job_offer_id}  -> SavedJob (201; 200 if already saved)
 *   DELETE /saved-jobs/{job_offer_id}  -> 204
 */
import { planned, request } from './client'
import type { ApplicationStatus } from './enums'
import { getJobOffer, type JobOfferListItem } from './jobOffers'
import { toListItem } from '@/mocks/offers'
import { mockSaved } from '@/mocks/saved'

export interface SavedJob {
  id: number
  job_offer: JobOfferListItem
  /** `saved`, or the status it already had when the offer was on the board before. */
  status: ApplicationStatus
  created_at: string
}

export const listSavedJobs = () =>
  planned(
    'saved',
    () => request<SavedJob[]>('/saved-jobs'),
    () => mockSaved.list(),
  )

export const saveJob = (job_offer_id: number) =>
  planned(
    'saved',
    () => request<SavedJob>('/saved-jobs', { method: 'POST', body: { job_offer_id } }),
    async () => mockSaved.add(toListItem(await getJobOffer(job_offer_id))),
  )

export const unsaveJob = (job_offer_id: number) =>
  planned(
    'saved',
    () => request<void>(`/saved-jobs/${job_offer_id}`, { method: 'DELETE' }),
    () => mockSaved.remove(job_offer_id),
  )
