import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { OfferSummary } from '@/api/jobOffers'

const summary: OfferSummary = {
  job_offer_id: 1,
  overview: 'Codesky builds booking APIs and looks for a junior Python developer.',
  responsibilities: ['Write FastAPI services'],
  must_have: ['1+ year of Python'],
  nice_to_have: [],
  benefits: ['Training budget'],
  salary: '12-16k PLN B2B',
  work_mode: 'hybrid',
  missing_info: ['Team size'],
  summary_with: 'fake/fake',
  prompt_version: 'offer-summary-v1',
  created_at: '2026-11-24T16:00:00Z',
}
const getOfferSummary = vi.fn()
const runOfferSummary = vi.fn()

vi.mock('@/api/jobOffers', () => ({
  MIN_SUMMARY_DESCRIPTION: 100,
  getOfferSummary: (id: number) => getOfferSummary(id) as unknown,
  runOfferSummary: (id: number) => runOfferSummary(id) as unknown,
}))

import { SummaryCard } from './SummaryCard'

const LONG = 'We build APIs. '.repeat(10)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SummaryCard', () => {
  it('shows a stored summary with its lists, pay and work mode', async () => {
    getOfferSummary.mockResolvedValue(summary)
    render(<SummaryCard offerId={1} description={LONG} />)

    expect(await screen.findByText(summary.overview)).toBeTruthy()
    expect(screen.getByText('Write FastAPI services')).toBeTruthy()
    expect(screen.getByText('12-16k PLN B2B')).toBeTruthy()
    expect(screen.getByText('Hybrid')).toBeTruthy()
    expect(screen.getByText(/Not in the posting: Team size/)).toBeTruthy()
    expect(screen.queryByText('Nice to have')).toBeNull() // empty lists are left out
    expect(screen.getByRole('button', { name: /summarise again/i })).toBeTruthy()
  })

  it('summarises on click when there is no summary yet', async () => {
    getOfferSummary.mockResolvedValue(null)
    runOfferSummary.mockResolvedValue(summary)
    render(<SummaryCard offerId={1} description={LONG} />)

    fireEvent.click(await screen.findByRole('button', { name: /^summarise$/i }))

    expect(runOfferSummary).toHaveBeenCalledWith(1)
    expect(await screen.findByText(summary.overview)).toBeTruthy()
  })

  it('cannot summarise an offer without a description', async () => {
    getOfferSummary.mockResolvedValue(null)
    render(<SummaryCard offerId={1} description="Python dev." />)

    const button = await screen.findByRole('button', { name: /^summarise$/i })
    expect((button as HTMLButtonElement).disabled).toBe(true)
    expect(await screen.findByText(/nothing to summarise/i)).toBeTruthy()
  })

  it('shows the error when the AI fails', async () => {
    getOfferSummary.mockResolvedValue(null)
    runOfferSummary.mockRejectedValue(new Error("The AI provider didn't answer, try again"))
    render(<SummaryCard offerId={1} description={LONG} />)

    fireEvent.click(await screen.findByRole('button', { name: /^summarise$/i }))

    expect(await screen.findByText(/didn't answer/)).toBeTruthy()
  })
})
