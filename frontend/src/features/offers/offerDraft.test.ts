import { describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import type { JobOfferCreate, JobOfferDraft } from '@/api/jobOffers'

import { fillFromDraft, missingFields, parseErrorMessage } from './offerDraft'

const PASTED = '  Junior Python Developer\nCodesky, Wrocław\n\nPython, FastAPI.  '

const draft: JobOfferDraft = {
  title: 'Junior Python Developer',
  company_name: 'Codesky',
  location: 'Wrocław',
  experience_level: 'junior',
  employment_type: 'b2b',
  deadline: '2026-12-15',
  technologies: ['Python', 'FastAPI'],
  url: 'https://codesky.pl/careers/1',
  description: PASTED.trim(),
  parsed_with: 'ollama/qwen2.5:3b',
}

const empty: JobOfferCreate = {
  title: '',
  company_name: '',
  url: '',
  location: '',
  experience_level: null,
  employment_type: null,
  deadline: null,
  technologies: [],
  description: '',
}

const nothingFound: JobOfferDraft = {
  ...draft,
  company_name: null,
  location: null,
  experience_level: null,
  employment_type: null,
  deadline: null,
  technologies: [],
  url: null,
}

describe('fillFromDraft', () => {
  it('fills every field the AI found', () => {
    expect(fillFromDraft(empty, draft, PASTED)).toEqual({
      title: 'Junior Python Developer',
      company_name: 'Codesky',
      url: 'https://codesky.pl/careers/1',
      location: 'Wrocław',
      experience_level: 'junior',
      employment_type: 'b2b',
      deadline: '2026-12-15',
      technologies: ['Python', 'FastAPI'],
      description: PASTED,
    })
  })

  it('puts the pasted text in the description exactly as it was', () => {
    expect(fillFromDraft(empty, draft, PASTED).description).toBe(PASTED)
  })

  it('keeps what the user typed where the AI found nothing', () => {
    const typed: JobOfferCreate = {
      ...empty,
      company_name: 'Typed company',
      url: 'https://typed.pl/job',
      location: 'Kraków',
      experience_level: 'middle',
      technologies: ['Go'],
    }

    const form = fillFromDraft(typed, nothingFound, PASTED)

    expect(form.company_name).toBe('Typed company')
    expect(form.url).toBe('https://typed.pl/job')
    expect(form.location).toBe('Kraków')
    expect(form.experience_level).toBe('middle')
    expect(form.technologies).toEqual(['Go'])
  })

  it('replaces what the user typed where the AI found something', () => {
    const form = fillFromDraft({ ...empty, company_name: 'Old' }, draft, PASTED)
    expect(form.company_name).toBe('Codesky')
  })
})

describe('missingFields', () => {
  it('is empty when the AI found everything', () => {
    expect(missingFields(draft)).toEqual([])
  })

  it('names what the AI did not find', () => {
    expect(missingFields(nothingFound)).toEqual([
      'company',
      'link',
      'location',
      'experience level',
      'employment type',
      'deadline',
      'technologies',
    ])
  })
})

describe('parseErrorMessage', () => {
  it('says the AI did not answer on 502', () => {
    const message = parseErrorMessage(new ApiError(502, "The AI provider didn't answer"))
    expect(message).toContain("The AI didn't answer")
    expect(message).toContain('fill the fields by hand')
  })

  it('shows the backend message for other errors', () => {
    expect(parseErrorMessage(new ApiError(422, 'text: too short'))).toBe('text: too short')
  })

  it('says the server is unreachable when fetch fails', () => {
    expect(parseErrorMessage(new TypeError('Failed to fetch'))).toContain('Could not reach')
  })
})
