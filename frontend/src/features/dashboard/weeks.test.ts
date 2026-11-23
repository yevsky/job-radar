import { describe, expect, it } from 'vitest'

import { applyStreak, mondayKey, padWeeks } from './weeks'

const week = (week_start: string, applied = 0) => ({ week_start, saved: 0, applied, replied: 0 })

describe('mondayKey', () => {
  it('finds the Monday of the week', () => {
    expect(mondayKey(new Date(2026, 10, 26))).toBe('2026-11-23') // Thursday
    expect(mondayKey(new Date(2026, 10, 29))).toBe('2026-11-23') // Sunday
    expect(mondayKey(new Date(2026, 10, 23))).toBe('2026-11-23') // Monday itself
  })
})

describe('padWeeks', () => {
  it('adds empty weeks before a short all-time history', () => {
    const result = padWeeks([week('2026-11-23', 4)], 'all', 4)
    expect(result.map((w) => w.week_start)).toEqual([
      '2026-11-02',
      '2026-11-09',
      '2026-11-16',
      '2026-11-23',
    ])
    expect(result.at(-1)?.applied).toBe(4)
  })

  it('leaves the fixed ranges alone', () => {
    const weekly = [week('2026-11-23')]
    expect(padWeeks(weekly, '30d')).toBe(weekly)
  })

  it('starts from this week when there is nothing yet', () => {
    const result = padWeeks([], 'all', 2, new Date(2026, 10, 25))
    expect(result.map((w) => w.week_start)).toEqual(['2026-11-16', '2026-11-23'])
  })
})

describe('applyStreak', () => {
  it('counts weeks in a row with an application', () => {
    expect(applyStreak([week('a', 1), week('b', 0), week('c', 2), week('d', 1)])).toBe(2)
  })

  it('does not break the streak on a quiet current week', () => {
    expect(applyStreak([week('a', 1), week('b', 3), week('c', 0)])).toBe(2)
  })

  it('is zero without applications', () => {
    expect(applyStreak([week('a'), week('b')])).toBe(0)
  })
})
