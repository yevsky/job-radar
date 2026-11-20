/** Backend: routers/job_offer.py (exists). */
import { existing, request } from './client'
import type { EmploymentType, ExperienceLevel, SourceKind } from './enums'
import { mockOffers } from '@/mocks/offers'

export interface JobOfferListItem {
  id: number
  title: string
  company_name: string
  location: string | null
  employment_type: EmploymentType | null
  experience_level: ExperienceLevel | null
  deadline: string | null
  technologies: string[]
}

export interface JobOfferPage {
  items: JobOfferListItem[]
  total: number
  limit: number
  offset: number
}

export interface JobOfferRead extends JobOfferListItem {
  source: SourceKind
  url: string
  is_active: boolean
  is_private: boolean
  description: string | null
  last_seen_at: string | null
  created_at: string
}

/** Body of POST /job-offers (JobOfferImport). */
export interface JobOfferCreate {
  title: string
  company_name: string
  url: string
  location?: string | null
  experience_level?: ExperienceLevel | null
  employment_type?: EmploymentType | null
  deadline?: string | null
  technologies?: string[]
  description?: string | null
}

export interface JobOfferFilters {
  technology: string[]
  location: string
  experience_level: ExperienceLevel[]
  employment_type: EmploymentType[]
}

export const emptyFilters: JobOfferFilters = {
  technology: [],
  location: '',
  experience_level: [],
  employment_type: [],
}

export function listJobOffers(
  filters: JobOfferFilters,
  limit: number,
  offset: number,
  signal?: AbortSignal,
): Promise<JobOfferPage> {
  return existing(
    () =>
      request<JobOfferPage>('/job-offers', {
        query: { ...filters, limit, offset },
        signal,
      }),
    () => mockOffers.list(filters, limit, offset),
  )
}

export const getJobOffer = (id: number, signal?: AbortSignal) =>
  existing(
    () => request<JobOfferRead>(`/job-offers/${id}`, { signal }),
    () => mockOffers.get(id),
  )

/** Saves a private offer; a URL we already know returns that offer (200 instead of 201). */
export const createJobOffer = (data: JobOfferCreate) =>
  existing(
    () => request<JobOfferRead>('/job-offers', { method: 'POST', body: data }),
    () => mockOffers.create(data, 'manual'),
  )

export const deleteJobOffer = (id: number) =>
  existing(
    () => request<void>(`/job-offers/${id}`, { method: 'DELETE' }),
    () => mockOffers.remove(id),
  )
