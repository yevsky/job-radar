import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ApplicationStats } from '@/api/applications'

import { RepliesCard } from './RepliesCard'

afterEach(cleanup)

/** 100 sent: 10 got past applying, 1 reached an offer, 20 were rejected right away. */
const stats: ApplicationStats = {
  range: 'all',
  funnel: [
    { stage: 'applied', reached: 100 },
    { stage: 'screening', reached: 10 },
    { stage: 'interview', reached: 4 },
    { stage: 'offer', reached: 1 },
    { stage: 'accepted', reached: 0 },
  ],
  outcomes: [
    { stage: 'applied', status: 'applied', count: 70 },
    { stage: 'applied', status: 'rejected', count: 20 },
    { stage: 'screening', status: 'rejected', count: 6 },
    { stage: 'interview', status: 'rejected', count: 3 },
    { stage: 'offer', status: 'declined', count: 1 },
  ],
  weekly: [],
  replied: 30,
}

const row = (label: string) => screen.getByText(label).closest('.reply-row')?.textContent

describe('RepliesCard', () => {
  it('gives every outcome as a share of everything sent', () => {
    render(<RepliesCard stats={stats} />)

    expect(row('Offer')).toBe('Offer11%')
    expect(row('Screening call')).toBe('Screening call1010%')
    expect(row('Rejected')).toContain('2929%')
    expect(row('No reply yet')).toBe('No reply yet7070%')
    expect(row('You declined')).toBe('You declined11%')
  })

  it('splits first replies into positive, negative and none', () => {
    render(<RepliesCard stats={stats} />)

    expect(screen.getByText(/First reply/).textContent).toBe(
      'First reply: 10 positive, 20 negative, 70 none',
    )
  })

  it('says so when nothing was sent', () => {
    render(<RepliesCard stats={{ ...stats, funnel: [], outcomes: [], replied: 0 }} />)

    expect(screen.getByText('Nothing sent in this period yet.')).toBeTruthy()
  })
})
