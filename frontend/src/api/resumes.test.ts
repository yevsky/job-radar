import { describe, expect, it } from 'vitest'

import { snapshotResume, type Resume } from './resumes'

const insights = {
  summary: 'x',
  industries: [],
  expertise: [],
  roles: [],
  growth: [],
  advice: null,
}

function cv(id: number, created: string, applied: string | null, withInsights = true): Resume {
  return {
    id,
    label: `CV ${id}`,
    file_name: 'cv.pdf',
    created_at: created,
    extracted: {
      desired_position: null,
      experience_level: null,
      skills: [],
      locations: [],
      employment_types: [],
      summary: null,
    },
    extracted_with: null,
    insights: withInsights ? insights : null,
    insights_with: null,
    applied_to_profile_at: applied,
  }
}

describe('snapshotResume', () => {
  it('picks the CV last applied to the profile', () => {
    const picked = snapshotResume([
      cv(1, '2026-11-01', '2026-11-02'),
      cv(2, '2026-11-03', '2026-11-10'),
      cv(3, '2026-11-20', null),
    ])
    expect(picked?.id).toBe(2)
  })

  it('falls back to the newest CV with a snapshot', () => {
    const picked = snapshotResume([
      cv(1, '2026-11-01', null),
      cv(2, '2026-11-03', null),
      cv(3, '2026-11-20', '2026-11-21', false),
    ])
    expect(picked?.id).toBe(2)
  })

  it('finds nothing when no CV has a snapshot', () => {
    expect(snapshotResume([cv(1, '2026-11-01', null, false)])).toBeUndefined()
  })
})
