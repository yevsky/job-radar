import { describe, expect, it } from 'vitest'

import { searchPosition } from './searchPosition'

describe('searchPosition', () => {
  it('writes the level as a word with a capital, not the raw value', () => {
    expect(
      searchPosition({ desired_position: 'Python Developer', experience_level: 'junior' }),
    ).toBe('Junior Python Developer')
  })

  it('does not add the level twice and capitalises the first letter', () => {
    expect(
      searchPosition({ desired_position: 'junior Python Developer', experience_level: 'junior' }),
    ).toBe('Junior Python Developer')
  })

  it('is empty without a position', () => {
    expect(searchPosition({ desired_position: null, experience_level: 'junior' })).toBe('')
  })
})
