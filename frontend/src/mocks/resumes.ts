import type { ProfileRead } from '@/api/profile'
import type { Resume, ResumeApply } from '@/api/resumes'

import { mockProfile } from './profile'
import { daysFromNow, newId, notFound } from './util'

const resumes: Resume[] = [
  {
    id: 1,
    label: 'Backend CV (English)',
    file_name: 'cv-backend-en.pdf',
    created_at: daysFromNow(-70),
    extracted: {
      desired_position: 'Python backend developer',
      experience_level: 'junior',
      skills: ['Python', 'FastAPI', 'PostgreSQL', 'SQLAlchemy', 'Docker', 'pytest', 'Git'],
      locations: ['Wrocław', 'Remote'],
      employment_types: ['full_time', 'b2b'],
      summary:
        'Engineering student with one year of internship experience building REST APIs in Python.',
    },
    extracted_with: 'fake/demo-model',
    applied_to_profile_at: daysFromNow(-69),
  },
  {
    id: 2,
    label: 'Full-stack CV',
    file_name: 'cv-fullstack.pdf',
    created_at: daysFromNow(-40),
    extracted: {
      desired_position: 'Full-stack developer',
      experience_level: 'junior',
      skills: ['Python', 'FastAPI', 'React', 'TypeScript', 'CSS', 'PostgreSQL'],
      locations: ['Wrocław', 'Kraków'],
      employment_types: ['full_time'],
      summary: 'Developer comfortable on both sides: FastAPI services and React interfaces.',
    },
    extracted_with: 'fake/demo-model',
    applied_to_profile_at: null,
  },
]

export const mockResumes = {
  list: () => [...resumes].sort((a, b) => b.created_at.localeCompare(a.created_at)),
  upload(file: File, label: string): Resume {
    const resume: Resume = {
      id: newId(),
      label: label || file.name.replace(/\.pdf$/i, ''),
      file_name: file.name,
      created_at: new Date().toISOString(),
      extracted: {
        desired_position: 'Backend developer',
        experience_level: 'junior',
        skills: ['Python', 'FastAPI', 'SQL', 'Linux', 'Git'],
        locations: ['Remote'],
        employment_types: ['full_time'],
        summary: 'Demo extraction: the real one comes from the AI module (milestone 8).',
      },
      extracted_with: 'fake/demo-model',
      applied_to_profile_at: null,
    }
    resumes.push(resume)
    return resume
  },
  apply(id: number, data: ResumeApply): ProfileRead {
    const resume = resumes.find((r) => r.id === id) ?? notFound('Resume')
    resume.applied_to_profile_at = new Date().toISOString()
    const patch: Partial<ProfileRead> = {}
    if (data.desired_position !== undefined) patch.desired_position = data.desired_position
    if (data.experience_level !== undefined) patch.experience_level = data.experience_level
    if (data.skills) patch.skills = data.skills
    if (data.locations) patch.preferred_locations = data.locations
    if (data.employment_types) patch.preferred_employment_types = data.employment_types
    return mockProfile.patch(patch)
  },
  remove(id: number): void {
    const index = resumes.findIndex((r) => r.id === id)
    if (index === -1) notFound('Resume')
    resumes.splice(index, 1)
  },
}
