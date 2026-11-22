import { describe, expect, it } from 'vitest'

import type { SearchResult, SearchSources } from '@/api/search'

import { activeSources, formatSalary, isRemote, monogram, similarTo, supports } from './searchUtils'

const result = (fields: Partial<SearchResult> = {}): SearchResult => ({
  title: 'Junior Python Developer',
  company_name: 'Codesky',
  url: 'https://example.com/1',
  found_via: 'tavily',
  ...fields,
})

describe('formatSalary', () => {
  it('shows a range with the currency and period', () => {
    const r = result({
      salary_min: 9000,
      salary_max: 12000,
      salary_currency: 'PLN',
      salary_period: 'month',
    })
    expect(formatSalary(r)).toBe('9 000–12 000 PLN / month')
  })

  it('shows one number when there is no range', () => {
    expect(
      formatSalary(result({ salary_max: 80, salary_currency: 'PLN', salary_period: 'hour' })),
    ).toBe('80 PLN / h')
  })

  it('is null without a salary', () => {
    expect(formatSalary(result())).toBeNull()
  })
})

describe('monogram', () => {
  it.each([
    ['Codesky', 'CO'],
    ['Heron Health', 'HH'],
    ['N-iX', 'NI'],
    ['', ''],
  ])('%s -> %s', (company, letters) => {
    expect(monogram(company)).toBe(letters)
  })
})

describe('isRemote', () => {
  it('is true only when the location says remote', () => {
    expect(isRemote(result({ location: 'Remote' }))).toBe(true)
    expect(isRemote(result({ location: 'Wrocław' }))).toBe(false)
    expect(isRemote(result({ location: null }))).toBe(false)
  })
})

describe('activeSources and supports', () => {
  const data: SearchSources = {
    available: ['tavily', 'jsearch'],
    chosen: ['jsearch'],
    features: { tavily: ['posted_within'], jsearch: ['country', 'posted_within', 'pages'] },
  }

  it('uses the chosen sources, or all when none is chosen', () => {
    expect(activeSources(data)).toEqual(['jsearch'])
    expect(activeSources({ ...data, chosen: null })).toEqual(['tavily', 'jsearch'])
    // a chosen source that was turned off falls back to all
    expect(activeSources({ ...data, chosen: ['fake'] })).toEqual(['tavily', 'jsearch'])
  })

  it('says if an active source uses a form field', () => {
    expect(supports(data, 'country')).toBe(true)
    expect(supports({ ...data, chosen: ['tavily'] }, 'country')).toBe(false)
    expect(supports({ available: ['x'], chosen: null }, 'country')).toBe(true) // older backend
  })
})

describe('similarTo', () => {
  it('ranks by shared technologies and leaves out the offer itself', () => {
    const target = result({
      url: 'a',
      technologies: ['Python', 'FastAPI'],
      experience_level: 'junior',
    })
    const both = result({ url: 'b', technologies: ['python', 'FastAPI'] })
    const one = result({ url: 'c', technologies: ['Python'] })
    const none = result({ url: 'd', technologies: ['Java'], experience_level: 'senior' })

    expect(similarTo(target, [target, one, none, both]).map((r) => r.url)).toEqual(['b', 'c'])
  })
})
