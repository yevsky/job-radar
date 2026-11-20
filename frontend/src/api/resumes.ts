/**
 * CVs ("resumes" table). Milestone 8: planned.
 *
 * Planned contract:
 *   GET    /resumes                       -> Resume[]
 *   POST   /resumes  (multipart: file=PDF, label) -> Resume (text extracted, file not kept)
 *   POST   /resumes/{id}/apply  ResumeApply -> ProfileRead (user picked what to copy)
 *   DELETE /resumes/{id}                  -> 204
 */
import { planned, request } from './client'
import type { EmploymentType, ExperienceLevel } from './enums'
import type { ProfileRead } from './profile'
import { mockResumes } from '@/mocks/resumes'

export interface ResumeExtracted {
  desired_position: string | null
  experience_level: ExperienceLevel | null
  skills: string[]
  locations: string[]
  employment_types: EmploymentType[]
  summary: string | null
}

export interface Resume {
  id: number
  label: string
  file_name: string
  created_at: string
  extracted: ResumeExtracted
  /** "provider/model" that did the extraction. */
  extracted_with: string | null
  applied_to_profile_at: string | null
}

/** Only the fields the user ticked are sent. */
export type ResumeApply = Partial<ResumeExtracted>

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
