/** Backend: routers/profile.py (exists). */
import { existing, request } from './client'
import type { EmploymentType, ExperienceLevel } from './enums'
import { mockProfile } from '@/mocks/profile'

export interface ProfileRead {
  first_name: string | null
  last_name: string | null
  bio: string | null
  experience_level: ExperienceLevel | null
  desired_position: string | null
  preferred_locations: string[]
  preferred_employment_types: EmploymentType[]
  skills: string[]
}

export type ProfileUpdate = Pick<
  ProfileRead,
  'first_name' | 'last_name' | 'bio' | 'experience_level' | 'desired_position'
>

export const getProfile = () =>
  existing(
    () => request<ProfileRead>('/profile/me'),
    () => mockProfile.get(),
  )

export const updateProfile = (data: ProfileUpdate) =>
  existing(
    () => request<ProfileRead>('/profile/me', { method: 'PUT', body: data }),
    () => mockProfile.update(data),
  )

export const setLocations = (locations: string[]) =>
  existing(
    () => request<ProfileRead>('/profile/me/locations', { method: 'PUT', body: { locations } }),
    () => mockProfile.patch({ preferred_locations: locations }),
  )

export const setEmploymentTypes = (employment_types: EmploymentType[]) =>
  existing(
    () =>
      request<ProfileRead>('/profile/me/employment-types', {
        method: 'PUT',
        body: { employment_types },
      }),
    () => mockProfile.patch({ preferred_employment_types: employment_types }),
  )

export const setSkills = (skills: string[]) =>
  existing(
    () => request<ProfileRead>('/profile/me/skills', { method: 'PUT', body: { skills } }),
    () => mockProfile.patch({ skills }),
  )

export const deleteProfile = () =>
  existing(
    () => request<void>('/profile/me', { method: 'DELETE' }),
    () => mockProfile.reset(),
  )
