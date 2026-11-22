import { describe, expect, it } from 'vitest'

import { scoreBand } from './scoreBand'

describe('scoreBand', () => {
  it.each([
    [100, 'Strong match'],
    [70, 'Strong match'],
    [69, 'Partial match'],
    [45, 'Partial match'],
    [44, 'Weak match'],
    [0, 'Weak match'],
  ])('%i is a %s', (score, label) => {
    expect(scoreBand(score).label).toBe(label)
  })
})
