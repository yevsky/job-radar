import { describe, expect, it } from 'vitest'

import { dayKey, greeting, pct } from './format'

describe('format helpers', () => {
  it('pct rounds and never divides by zero', () => {
    expect(pct(1, 3)).toBe(33)
    expect(pct(5, 0)).toBe(0)
  })

  it('dayKey is the local date with leading zeros', () => {
    expect(dayKey(new Date(2026, 0, 5, 23, 30))).toBe('2026-01-05')
  })

  it.each([
    [3, 'Good night'],
    [9, 'Good morning'],
    [14, 'Good afternoon'],
    [21, 'Good evening'],
  ])('greeting at %i:00 is %s', (hour, text) => {
    expect(greeting(new Date(2026, 10, 22, hour))).toBe(text)
  })
})
