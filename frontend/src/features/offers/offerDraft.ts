/** Turning the AI's draft of a pasted posting into the add-offer form. */
import { ApiError } from '@/api/client'
import type { JobOfferCreate, JobOfferDraft } from '@/api/jobOffers'

/**
 * The form after reading a posting. A field the AI found replaces what is there; a field it
 * didn't find keeps what the user already typed. The description is the pasted text as it is.
 */
export function fillFromDraft(
  form: JobOfferCreate,
  draft: JobOfferDraft,
  pasted: string,
): JobOfferCreate {
  return {
    title: draft.title || form.title,
    company_name: draft.company_name ?? form.company_name,
    url: draft.url ?? form.url,
    location: draft.location ?? form.location,
    experience_level: draft.experience_level ?? form.experience_level,
    employment_type: draft.employment_type ?? form.employment_type,
    deadline: draft.deadline ?? form.deadline,
    technologies: draft.technologies.length > 0 ? draft.technologies : form.technologies,
    description: pasted,
  }
}

const FIELD_NAMES: [keyof JobOfferDraft, string][] = [
  ['company_name', 'company'],
  ['url', 'link'],
  ['location', 'location'],
  ['experience_level', 'experience level'],
  ['employment_type', 'employment type'],
  ['deadline', 'deadline'],
  ['technologies', 'technologies'],
]

/** Names of the fields the AI didn't find, to tell the user what to fill by hand. */
export function missingFields(draft: JobOfferDraft): string[] {
  return FIELD_NAMES.filter(([key]) => {
    const value = draft[key]
    return value === null || (Array.isArray(value) && value.length === 0)
  }).map(([, name]) => name)
}

/** A message that says what went wrong and what the user can do. */
export function parseErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 502) {
      return "The AI didn't answer (is Ollama running?). Try again, or fill the fields by hand."
    }
    return err.message
  }
  if (err instanceof TypeError) {
    return 'Could not reach the server. Check that the backend is running and try again.'
  }
  return err instanceof Error ? err.message : 'Could not read the posting'
}
