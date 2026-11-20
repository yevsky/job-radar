import type { ProfileRead, ProfileUpdate } from '@/api/profile'

const emptyProfile: ProfileRead = {
  first_name: null,
  last_name: null,
  bio: null,
  experience_level: null,
  desired_position: null,
  preferred_locations: [],
  preferred_employment_types: [],
  skills: [],
}

let profile: ProfileRead = {
  first_name: 'Alex',
  last_name: 'Nowak',
  bio: 'Backend developer finishing an engineering degree. I like typed Python, clean APIs and small, well-tested services.',
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
