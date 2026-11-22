/**
 * Backend: routers/search.py.
 * The form is position (with the level in it, e.g. "Junior Python developer"), cities,
 * country, posted within and page. Contract, technologies and level filters were dropped
 * on 2026-11-18: the sources handle them differently and the position already says it.
 */
import { existing, planned, request } from './client'
import type { JobOfferCreate, JobOfferRead } from './jobOffers'
import { mockSearch } from '@/mocks/search'

export type PostedWithin = 'day' | 'week' | 'month'

export interface SearchQuery {
  position: string | null
  /** Cities; "Remote" also keeps remote offers. Offers from other known cities are left out. */
  locations: string[]
  /** ISO code, e.g. "pl". */
  country: string
  posted_within: PostedWithin | null
}

export const MAX_LOCATIONS = 5
export const MAX_PAGE = 10

/** Countries the form offers; the backend accepts any two-letter code. */
export const COUNTRIES: { code: string; label: string }[] = [
  { code: 'pl', label: 'Poland' },
  { code: 'de', label: 'Germany' },
  { code: 'gb', label: 'United Kingdom' },
  { code: 'nl', label: 'Netherlands' },
  { code: 'cz', label: 'Czechia' },
  { code: 'us', label: 'United States' },
]

export type SalaryPeriod = 'hour' | 'month' | 'year'

export interface SearchResult extends JobOfferCreate {
  found_via: string
  /** Planned, optional: what the source knows about pay and posting date (JSearch has these). */
  salary_min?: number | null
  salary_max?: number | null
  salary_currency?: string | null
  salary_period?: SalaryPeriod | null
  posted_at?: string | null
}

/** Why a found offer is not among the results (the backend's HiddenReason). */
export type HiddenReason = 'list_page' | 'closed' | 'expired' | 'other_city' | 'other_level'

export interface HiddenResult extends SearchResult {
  hidden_because: HiddenReason
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  errors: { source: string; message: string }[]
  page: number
  /** True if a source may have another page. */
  has_more: boolean
  /** Results left out: list pages, other cities, levels far from the position. */
  hidden?: number
  /** The left-out offers that could be read, with the reason. */
  hidden_results?: HiddenResult[]
  /** Only page 1 counts as a search. */
  searches_left_today?: number
}

/** Form fields a source uses besides position and cities. */
export type SourceFeature = 'country' | 'posted_within' | 'pages'

/** GET/PUT /search/sources: which search engines this user asks. `chosen: null` = all. */
export interface SearchSources {
  available: string[]
  chosen: string[] | null
  features?: Record<string, SourceFeature[]>
}

export const isEmptyQuery = (q: SearchQuery) => !q.position?.trim()

export const getSearchDefaults = () =>
  existing(
    () => request<SearchQuery>('/search/defaults'),
    () => mockSearch.defaults(),
  )

export const runSearch = (query: SearchQuery, page = 1) =>
  planned(
    'search',
    () => request<SearchResponse>('/search', { method: 'POST', body: { ...query, page } }),
    () => mockSearch.run(query, page),
  )

export const getSearchSources = () =>
  existing(
    () => request<SearchSources>('/search/sources'),
    () => mockSearch.sources(),
  )

/** `null` means "all available sources" (also what the backend stores for that). */
export const setSearchSources = (sources: string[] | null) =>
  existing(
    () => request<SearchSources>('/search/sources', { method: 'PUT', body: { sources } }),
    () => mockSearch.setSources(sources),
  )

/** GET /search/usage: how many searches are left today. */
export interface SearchUsage {
  daily_limit: number
  used_today: number
  left_today: number
}

export const getSearchUsage = () =>
  existing(
    () => request<SearchUsage>('/search/usage'),
    () => mockSearch.usage(),
  )

/**
 * Planned contract: POST /search/results with a SearchResult body ->
 * JobOfferRead (201 new, 200 already known), saved with source='search' and found_via.
 */
export const saveSearchResult = (result: SearchResult) =>
  planned(
    'search-save',
    () => request<JobOfferRead>('/search/results', { method: 'POST', body: result }),
    () => mockSearch.save(result),
  )
