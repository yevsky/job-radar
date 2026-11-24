/**
 * CVs ("resumes" table). Milestone 8: planned.
 *
 * Planned contract:
 *   GET    /resumes                       -> Resume[]
 *   POST   /resumes  (multipart: file=PDF, label) -> Resume (text extracted, file not kept)
 *   POST   /resumes/{id}/apply  ResumeApply -> ProfileRead (user picked what to copy)
 *   POST   /resumes/{id}/insights        -> Resume (the career snapshot written again)
 *   DELETE /resumes/{id}                  -> 204
 */
import { planned, request } from './client'
import type { EmploymentType, ExperienceLevel } from './enums'
import type { ProfileRead } from './profile'
import { mockResumes } from '@/mocks/resumes'

export interface ResumeExtracted {
  desired_position: string | null
  experience_level: ExperienceLevel | null
  /** Years of work, counted by the backend from the CV's job dates. */
  experience_years?: number | null
  skills: string[]
  locations: string[]
  employment_types: EmploymentType[]
  summary: string | null
}

/**
 * The CV's career snapshot for the profile page (ResumeInsights), written by a second AI call
 * after the extraction. The level and years are in `extracted`, counted by code.
 */
export interface ResumeInsights {
  /** 3-4 sentences in the first person: how the person would describe themself. */
  summary: string
  /** Fields the person works in, e.g. 'AI/ML automation'. */
  industries: string[]
  /** Broader areas than single skills, e.g. 'REST API development'. */
  expertise: string[]
  /** Job titles to search for, fitting the level. */
  roles: string[]
  /** What to learn next. */
  growth: string[]
  /** 2-3 sentences of advice for the job search. */
  advice: string | null
}

export interface Resume {
  id: number
  label: string
  file_name: string
  created_at: string
  extracted: ResumeExtracted
  /** "provider/model" that did the extraction. */
  extracted_with: string | null
  /** null until the AI has written it (or if it failed: POST /resumes/{id}/insights). */
  insights?: ResumeInsights | null
  insights_with?: string | null
  applied_to_profile_at: string | null
}

/**
 * Only the fields the user ticked are sent. Skills are added to the profile's by default;
 * `skills_mode: 'replace'` keeps only the CV's.
 */
export type ResumeApply = Partial<Omit<ResumeExtracted, 'summary' | 'experience_years'>> & {
  skills_mode?: 'add' | 'replace'
}

export const listResumes = () =>
  planned(
    'resumes',
    () => request<Resume[]>('/resumes'),
    () => mockResumes.list(),
  )

export function uploadResume(file: File, label: string): Promise<Resume> {
  const form = new FormData()
  form.append('file', file)
  form.append('label', label)
  return planned(
    'resumes',
    () => request<Resume>('/resumes', { method: 'POST', body: form }),
    () => mockResumes.upload(file, label),
  )
}

export const applyResume = (id: number, data: ResumeApply) =>
  planned(
    'resumes',
    () => request<ProfileRead>(`/resumes/${id}/apply`, { method: 'POST', body: data }),
    () => mockResumes.apply(id, data),
  )

export const deleteResume = (id: number) =>
  planned(
    'resumes',
    () => request<void>(`/resumes/${id}`, { method: 'DELETE' }),
    () => mockResumes.remove(id),
  )

/** Let the AI write the CV's career snapshot again. 502 if the AI didn't answer. */
export const makeInsights = (id: number) =>
  planned(
    'resumes',
    () => request<Resume>(`/resumes/${id}/insights`, { method: 'POST' }),
    () => mockResumes.insights(id),
  )

/**
 * The CV whose snapshot the profile shows: the one last applied to the profile, else the
 * newest one that has a snapshot.
 */
export function snapshotResume(resumes: Resume[]): Resume | undefined {
  const withInsights = resumes.filter((r) => r.insights)
  const applied = withInsights
    .filter((r) => r.applied_to_profile_at)
    .sort((a, b) => (b.applied_to_profile_at ?? '').localeCompare(a.applied_to_profile_at ?? ''))
  return applied[0] ?? [...withInsights].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
}
