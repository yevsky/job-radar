import type { ExperienceLevel } from '@/api/enums'
import type { ProfileRead } from '@/api/profile'

export interface Suggestion {
  text: string
  /** Put `text` in the message box to finish (paste a posting) instead of sending it */
  prefill?: boolean
}

export const PASTE_OFFER = 'Add this job offer to my offers:\n'

const levelWord: Record<ExperienceLevel, string> = {
  trainee: 'trainee',
  junior: 'junior',
  middle: 'mid-level',
  senior: 'senior',
  lead: 'lead',
}

/**
 * The welcome suggestions, written from the user's profile, so "Find jobs" asks for their
 * level, position and city, not for an example the profile doesn't match.
 */
export function suggestionsFor(profile: ProfileRead | null): Suggestion[] {
  const position = profile?.desired_position?.trim() || profile?.skills[0] || ''
  const level = profile?.experience_level ? levelWord[profile.experience_level] : ''
  // "Junior Python developer" already has its level
  const hasLevel = level !== '' && position.toLowerCase().includes(level.split('-')[0])
  const what = [hasLevel ? '' : level, position].filter(Boolean).join(' ')
  const city = profile?.preferred_locations[0]

  const search = what
    ? `Find ${what} jobs${city ? ` in ${city}` : ''}`
    : 'Find jobs that fit my profile'
  const skills = position
    ? `Which skills from my CV fit ${position} jobs best?`
    : 'Which jobs fit the skills in my CV?'

  return [
    { text: search },
    { text: 'What interviews do I have in the next two weeks?' },
    { text: 'How are my applications going?' },
    { text: skills },
    { text: 'Add a job offer from a posting', prefill: true },
  ]
}
