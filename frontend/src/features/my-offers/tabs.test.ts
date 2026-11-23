import { describe, expect, it } from 'vitest'

import type { MyOffer } from '@/api/jobOffers'

import { countByTab, inTab } from './tabs'

function offer(overrides: Partial<MyOffer>): MyOffer {
  return {
    id: 1,
    title: 'Backend Developer',
    company_name: 'Codesky',
    location: null,
    employment_type: null,
    experience_level: null,
    deadline: null,
    technologies: [],
    source: 'posted',
    found_via: null,
    url: 'https://example.com/1',
    is_active: true,
    is_private: false,
    added_at: '2026-11-20T10:00:00Z',
    application: null,
    ...overrides,
  }
}

const app = (status: NonNullable<MyOffer['application']>['status']) => ({
  id: 7,
  status,
  updated_at: '2026-11-21T10:00:00Z',
})

describe('My offers tabs', () => {
  it('puts a saved job board offer under Saved only', () => {
    const o = offer({ application: app('saved') })
    expect(inTab(o, 'saved')).toBe(true)
    expect(inTab(o, 'applied')).toBe(false)
    expect(inTab(o, 'manual')).toBe(false)
  })

  it('counts every status past saved as Applied, rejected too', () => {
    expect(inTab(offer({ application: app('interview') }), 'applied')).toBe(true)
    expect(inTab(offer({ application: app('rejected') }), 'applied')).toBe(true)
    expect(inTab(offer({}), 'applied')).toBe(false)
  })

  it('sorts offers you added by where they came from', () => {
    const fromSearch = offer({ is_private: true, source: 'search', found_via: 'jsearch' })
    expect(inTab(fromSearch, 'search')).toBe(true)
    expect(inTab(fromSearch, 'manual')).toBe(false)
    expect(inTab(offer({ is_private: true, source: 'manual' }), 'manual')).toBe(true)
  })

  it('does not count an imported public offer as added by you', () => {
    expect(inTab(offer({ source: 'manual', application: app('saved') }), 'manual')).toBe(false)
  })

  it('counts each tab', () => {
    const counts = countByTab([
      offer({ id: 1, application: app('saved') }),
      offer({ id: 2, is_private: true, source: 'search', application: app('applied') }),
      offer({ id: 3, is_private: true, source: 'manual' }),
    ])
    expect(counts).toEqual({ all: 3, saved: 1, applied: 1, manual: 1, search: 1 })
  })
})
