import type { ProfileRead } from '@/api/profile'
import { experienceLabel } from '@/lib/labels'

/**
 * The position the search form starts with, written the way the backend does it
 * (GET /search/defaults): 'Junior Python developer'. The level isn't added when the position
 * already names one, and the first letter is a capital.
 */
export function searchPosition(
  profile: Pick<ProfileRead, 'desired_position' | 'experience_level'>,
) {
  const own = profile.desired_position?.trim()
  if (!own) return ''
  const position = own[0].toUpperCase() + own.slice(1)
  const namesLevel = /\b(intern|trainee|junior|mid|middle|senior|lead)\b/i.test(position)
  if (!profile.experience_level || namesLevel) return position
  return `${experienceLabel[profile.experience_level]} ${position}`
}
