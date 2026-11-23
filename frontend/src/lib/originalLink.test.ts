import { describe, expect, it } from 'vitest'

import { hasOriginal } from './originalLink'

describe('hasOriginal', () => {
  it('is false for a posted demo offer, which lives only in the app', () => {
    expect(hasOriginal('https://jobradar.local/offers/brightfold-junior-python-developer')).toBe(
      false,
    )
  })

  it('is true for a posting on a job board', () => {
    expect(hasOriginal('https://justjoin.it/job-offer/itlt-junior-python-developer')).toBe(true)
  })

  it('is false for something that is not a link', () => {
    expect(hasOriginal('not a link')).toBe(false)
  })
})
