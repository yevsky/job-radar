/** Backend: routers/job_offer.py (exists). */
import { existing, request } from './client'
import type { ApplicationStatus, EmploymentType, ExperienceLevel, SourceKind } from './enums'
import { mockMyOffers } from '@/mocks/myOffers'
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
  /** Which search source found it (e.g. 'jsearch'), for offers kept from a search. */
  found_via: string | null
  url: string
  is_active: boolean
  is_private: boolean
  description: string | null
  last_seen_at: string | null
  created_at: string
}

/** One row of GET /job-offers/mine: an offer you added, or a public one you track. */
export interface MyOffer extends JobOfferListItem {
  source: SourceKind
  found_via: string | null
  url: string
  is_active: boolean
  /** true: you added it (only you see it). false: a job board offer you saved or applied to. */
  is_private: boolean
  /** When you added it, or started tracking it. */
  added_at: string
  application: { id: number; status: ApplicationStatus; updated_at: string } | null
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

/** Pasted posting limits, the same as JobOfferParseRequest in backend/app/schemas/ai.py. */
export const MIN_POSTING_LENGTH = 50
export const MAX_POSTING_LENGTH = 20_000

/** Answer of POST /job-offers/parse (JobOfferParseResponse): a draft to check. Nothing is saved. */
export interface JobOfferDraft {
  title: string
  company_name: string | null
  location: string | null
  experience_level: ExperienceLevel | null
  employment_type: EmploymentType | null
  /** A day, 'YYYY-MM-DD'. */
  deadline: string | null
  technologies: string[]
  /** The link the user gave, or the first link found in the text. */
  url: string | null
  /** The pasted text. */
  description: string
  /** Provider and model, e.g. 'ollama/qwen2.5:3b'. */
  parsed_with: string
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

/** Offers you added yourself or track (saved, applied…), newest first. */
export const listMyOffers = (signal?: AbortSignal) =>
  existing(
    () => request<MyOffer[]>('/job-offers/mine', { signal }),
    () => mockMyOffers.list(),
  )

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

/** The AI reads a pasted posting into form fields. Saves nothing; 502 if the AI didn't answer. */
export const parseJobOffer = (text: string) =>
  existing(
    () => request<JobOfferDraft>('/job-offers/parse', { method: 'POST', body: { text } }),
    () => mockOffers.parse(text),
  )

export const deleteJobOffer = (id: number) =>
  existing(
    () => request<void>(`/job-offers/${id}`, { method: 'DELETE' }),
    () => mockOffers.remove(id),
  )
