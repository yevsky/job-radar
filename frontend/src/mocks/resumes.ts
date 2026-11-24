import type { ProfileRead } from '@/api/profile'
import type { Resume, ResumeApply, ResumeInsights } from '@/api/resumes'

import { mockProfile } from './profile'
import { daysFromNow, newId, notFound } from './util'

const backendInsights: ResumeInsights = {
  summary:
    'I am a junior Python developer finishing my engineering degree, with a year of internship building REST APIs with FastAPI and PostgreSQL. I enjoy clean, tested backend code and automating the boring parts. I am looking for a junior backend role in Wrocław or remote.',
  industries: ['Software engineering', 'Backend services'],
  expertise: [
    'REST API development',
    'SQL and database design',
    'Test automation (pytest)',
    'Containerised deployments (Docker)',
  ],
  roles: ['Junior Backend Developer', 'Python Developer', 'Junior Software Engineer'],
  growth: ['Cloud platforms (AWS)', 'Message queues', 'Async Python'],
  advice:
    'Look for junior backend roles that use FastAPI or Django. Mention your internship projects with numbers, and add a small deployed project to show Docker in practice.',
}

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
    insights: backendInsights,
    insights_with: 'fake/demo-model',
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
    insights: null,
    insights_with: null,
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
      insights: backendInsights,
      insights_with: 'fake/demo-model',
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
  insights(id: number): Resume {
    const resume = resumes.find((r) => r.id === id) ?? notFound('Resume')
    resume.insights = {
      ...backendInsights,
      roles: resume.extracted.desired_position
        ? [resume.extracted.desired_position, ...backendInsights.roles.slice(0, 2)]
        : backendInsights.roles,
    }
    resume.insights_with = 'fake/demo-model'
    return { ...resume }
  },
  remove(id: number): void {
    const index = resumes.findIndex((r) => r.id === id)
    if (index === -1) notFound('Resume')
    resumes.splice(index, 1)
  },
}
