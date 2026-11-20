/**
 * Applications, status history, calendar and stats. Milestone 9: planned.
 *
 * Planned contract:
 *   GET   /applications                          -> Application[]
 *   POST  /applications {job_offer_id, status?, resume_id?, notes?, applied_at?} -> Application
 *   PATCH /applications/{id} {status?, notes?, applied_at?, interview_at?, resume_id?} -> Application
 *         (a status change also writes a row to application_status_changes)
 *   DELETE /applications/{id}                    -> 204
 *   GET   /applications/{id}/history             -> StatusChange[]
 *   GET   /applications/calendar?from=&to=       -> CalendarEvent[]  (dates are YYYY-MM-DD)
 *   GET   /applications/stats?range=30d|90d|all  -> ApplicationStats
 */
import { planned, request } from './client'
import type { ApplicationStatus, FunnelStage } from './enums'
import { getJobOffer, type JobOfferListItem } from './jobOffers'
import { mockApplications } from '@/mocks/applications'
import { toListItem } from '@/mocks/offers'

export interface Application {
  id: number
  job_offer: JobOfferListItem
  status: ApplicationStatus
  resume_id: number | null
  notes: string | null
  applied_at: string | null
  interview_at: string | null
  created_at: string
  updated_at: string
}

export interface ApplicationCreate {
  job_offer_id: number
  status?: ApplicationStatus
  resume_id?: number | null
  notes?: string | null
  applied_at?: string | null
}

export type ApplicationUpdate = Partial<
  Pick<Application, 'status' | 'notes' | 'applied_at' | 'interview_at' | 'resume_id'>
>

export interface StatusChange {
  status: ApplicationStatus
  changed_at: string
}

export type CalendarEventKind = 'applied' | 'status_change' | 'interview' | 'deadline'

export interface CalendarEvent {
  date: string
  kind: CalendarEventKind
  title: string
  company_name: string
  job_offer_id: number
  application_id: number | null
  status: ApplicationStatus | null
  /** Only interviews have a time. */
  time: string | null
}

export type StatsRange = '30d' | '90d' | 'all'

export interface ApplicationStats {
  range: StatsRange
  /** How many applications reached each stage (from the status history). */
  funnel: { stage: FunnelStage; reached: number }[]
  /** Where the ones that stopped at a stage are now, e.g. {stage:'screening', status:'rejected'}. */
  outcomes: { stage: FunnelStage; status: ApplicationStatus; count: number }[]
  /** Per ISO week (Monday): offers saved and applications sent. */
  weekly: { week_start: string; saved: number; applied: number }[]
}

export const listApplications = () =>
  planned(
    'applications',
    () => request<Application[]>('/applications'),
    () => mockApplications.list(),
  )

export const createApplication = (data: ApplicationCreate) =>
  planned(
    'applications',
    () => request<Application>('/applications', { method: 'POST', body: data }),
    async () => mockApplications.create(data, toListItem(await getJobOffer(data.job_offer_id))),
  )

export const updateApplication = (id: number, data: ApplicationUpdate) =>
  planned(
    'applications',
    () => request<Application>(`/applications/${id}`, { method: 'PATCH', body: data }),
    () => mockApplications.update(id, data),
  )

export const deleteApplication = (id: number) =>
  planned(
    'applications',
    () => request<void>(`/applications/${id}`, { method: 'DELETE' }),
    () => mockApplications.remove(id),
  )

export const getApplicationHistory = (id: number) =>
  planned(
    'applications',
    () => request<StatusChange[]>(`/applications/${id}/history`),
    () => mockApplications.history(id),
  )

export const getCalendar = (from: string, to: string) =>
  planned(
    'calendar',
    () => request<CalendarEvent[]>('/applications/calendar', { query: { from, to } }),
    () => mockApplications.calendar(from, to),
  )

export const getStats = (range: StatsRange) =>
  planned(
    'stats',
    () => request<ApplicationStats>('/applications/stats', { query: { range } }),
    () => mockApplications.stats(range),
  )
