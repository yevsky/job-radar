/**
 * AI match analysis ("How you match"). Milestone 8: planned.
 *
 * Planned contract:
 *   GET  /job-offers/{id}/analysis              -> AiAnalysis (latest) or 404 "No analysis yet"
 *   POST /job-offers/{id}/analysis {resume_id?} -> AiAnalysis (runs the model, stores the row)
 */
import { ApiError, planned, request } from './client'
import { getJobOffer } from './jobOffers'
import { getProfile } from './profile'
import { mockAnalysis } from '@/mocks/analysis'

export interface AiAnalysis {
  id: number
  job_offer_id: number
  resume_id: number | null
  /** 0-100 from a fixed rubric. */
  score: number
  summary: string | null
  reasons: string[]
  red_flags: string[]
  /** Decided by code from the model's requirement-to-skill mapping. */
  matched_skills: string[]
  missing_skills: string[]
  provider: string
  model: string
  prompt_version: string
  created_at: string
}

/** Latest analysis, or null if the offer hasn't been analysed yet. */
export function getAnalysis(offerId: number): Promise<AiAnalysis | null> {
  return planned(
    'analysis',
    async () => {
      try {
        return await request<AiAnalysis>(`/job-offers/${offerId}/analysis`)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404 && !err.isMissingRoute) return null
        throw err
      }
    },
    () => mockAnalysis.get(offerId),
  )
}

export const runAnalysis = (offerId: number, resumeId: number | null) =>
  planned(
    'analysis',
    () =>
      request<AiAnalysis>(`/job-offers/${offerId}/analysis`, {
        method: 'POST',
        body: { resume_id: resumeId },
      }),
    async () => mockAnalysis.run(await getJobOffer(offerId), await getProfile(), resumeId),
  )
