import { describe, expect, it } from 'vitest'

import { tipPosition } from './chartTip'

describe('tipPosition', () => {
  it('centres the tooltip in the middle of the chart', () => {
    expect(tipPosition(0.5)).toEqual({
      left: '50%',
      transform: 'translate(-50%, calc(-100% - 10px))',
    })
  })

  it('hangs inwards near the left edge, never past it', () => {
    expect(tipPosition(0.1)).toEqual({
      left: 'max(0px, calc(10% - 16px))',
      transform: 'translateY(calc(-100% - 10px))',
    })
  })

  it('is anchored by its right side near the right edge, never past it', () => {
    expect(tipPosition(1).right).toBe('max(0px, calc(0% - 16px))')
    expect(tipPosition(1).left).toBeUndefined()
  })
})
