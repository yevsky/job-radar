import type { ProfileRead, ProfileUpdate } from '@/api/profile'

const emptyProfile: ProfileRead = {
  experience_level: null,
  desired_position: null,
  preferred_locations: [],
  preferred_employment_types: [],
  skills: [],
}

let profile: ProfileRead = {
  experience_level: 'junior',
  desired_position: 'Python backend developer',
  preferred_locations: ['Wrocław', 'Remote'],
  preferred_employment_types: ['full_time', 'b2b'],
  skills: ['Python', 'FastAPI', 'PostgreSQL', 'SQLAlchemy', 'Docker', 'pytest', 'TypeScript'],
}

export const mockProfile = {
  get: (): ProfileRead => profile,
  update(data: ProfileUpdate): ProfileRead {
    profile = { ...profile, ...data }
    return profile
  },
  patch(data: Partial<ProfileRead>): ProfileRead {
    profile = { ...profile, ...data }
    return profile
  },
  reset(): void {
    profile = { ...emptyProfile }
  },
}
