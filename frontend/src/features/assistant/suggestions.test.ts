import { describe, expect, it } from 'vitest'

import type { ProfileRead } from '@/api/profile'

import { suggestionsFor } from './suggestions'

const profile: ProfileRead = {
  first_name: null,
  last_name: null,
  bio: null,
  experience_level: 'senior',
  desired_position: 'Backend developer',
  preferred_locations: ['Kraków', 'Wrocław'],
  preferred_employment_types: [],
  skills: ['Go', 'Kubernetes'],
}

const texts = (p: ProfileRead | null) => suggestionsFor(p).map((s) => s.text)

describe('suggestionsFor', () => {
  it('asks for the level, position and first city of the profile', () => {
    expect(texts(profile)).toContain('Find senior Backend developer jobs in Kraków')
    expect(texts(profile)).toContain('Which skills from my CV fit Backend developer jobs best?')
  })

  it('does not repeat a level the position already has', () => {
    const p = { ...profile, experience_level: 'junior' as const, desired_position: 'Junior QA' }
    expect(texts(p)).toContain('Find Junior QA jobs in Kraków')
  })

  it('uses the first skill without a position, and no city without one', () => {
    const p = { ...profile, desired_position: null, preferred_locations: [] }
    expect(texts(p)).toContain('Find senior Go jobs')
    expect(texts(p)).toContain('Which skills from my CV fit Go jobs best?')
  })

  it('stays general without a profile', () => {
    expect(texts(null)).toContain('Find jobs that fit my profile')
    expect(texts(null)).toContain('Which jobs fit the skills in my CV?')
    expect(texts(null).join(' ')).not.toMatch(/junior|Python|Wrocław|backend/i)
  })

  it('offers adding a pasted posting, which fills the box instead of sending', () => {
    const add = suggestionsFor(null).find((s) => s.prefill)
    expect(add?.text).toBe('Add a job offer from a posting')
  })
})
