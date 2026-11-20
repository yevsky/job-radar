import type { AiAnalysis } from '@/api/analysis'
import type { JobOfferRead } from '@/api/jobOffers'
import type { ProfileRead } from '@/api/profile'

import { newId } from './util'

const store = new Map<number, AiAnalysis>()

/** A deterministic stand-in for the AI: compares skills, then writes plausible reasons. */
function analyse(offer: JobOfferRead, profile: ProfileRead, resumeId: number | null): AiAnalysis {
  const mine = new Set(profile.skills.map((s) => s.toLowerCase()))
  const matched = offer.technologies.filter((t) => mine.has(t.toLowerCase()))
  const missing = offer.technologies.filter((t) => !mine.has(t.toLowerCase()))
  const levelOk = !offer.experience_level || offer.experience_level === profile.experience_level
  const locationOk =
    !offer.location ||
    profile.preferred_locations.some((l) => l.toLowerCase() === offer.location!.toLowerCase())

  const skillShare = offer.technologies.length ? matched.length / offer.technologies.length : 0.5
  const score = Math.round(skillShare * 70 + (levelOk ? 20 : 5) + (locationOk ? 10 : 0))

  const reasons = [
    matched.length
      ? `You already use ${matched.slice(0, 3).join(', ')}, which the offer asks for.`
      : 'None of the listed technologies are on your profile yet.',
    levelOk
      ? `The ${offer.experience_level ?? 'stated'} level fits your experience.`
      : `The offer targets ${offer.experience_level} level, yours is ${profile.experience_level ?? 'not set'}.`,
  ]
  if (locationOk && offer.location)
    reasons.push(`${offer.location} is one of your preferred locations.`)

  const red_flags: string[] = []
  if (offer.experience_level === 'senior' || offer.experience_level === 'lead')
    red_flags.push('Asks for several years of experience.')
  if (offer.deadline && new Date(offer.deadline).getTime() - Date.now() < 4 * 86_400_000)
    red_flags.push('The deadline is in less than 4 days.')
  if (!offer.description) red_flags.push('No description, so the match is based on the title only.')

  return {
    id: newId(),
    job_offer_id: offer.id,
    resume_id: resumeId,
    score: Math.min(score, 100),
    summary:
      score >= 70
        ? 'A strong match: apply soon.'
        : score >= 45
          ? 'A partial match: worth a look if the missing skills are learnable.'
          : 'A weak match for your current profile.',
    reasons,
    red_flags,
    matched_skills: matched,
    missing_skills: missing,
    provider: 'fake',
    model: 'demo-model',
    prompt_version: 'match-v1',
    created_at: new Date().toISOString(),
  }
}

export const mockAnalysis = {
  get: (offerId: number) => store.get(offerId) ?? null,
  run(offer: JobOfferRead, profile: ProfileRead, resumeId: number | null): AiAnalysis {
    const result = analyse(offer, profile, resumeId)
    store.set(offer.id, result)
    return result
  },
}
