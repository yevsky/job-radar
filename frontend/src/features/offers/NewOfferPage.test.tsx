import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import { createJobOffer, parseJobOffer, type JobOfferDraft } from '@/api/jobOffers'

import { NewOfferPage } from './NewOfferPage'

vi.mock('@/api/jobOffers', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/jobOffers')>()),
  parseJobOffer: vi.fn(),
  createJobOffer: vi.fn(),
}))

const parse = vi.mocked(parseJobOffer)
const create = vi.mocked(createJobOffer)

const POSTING =
  'Junior Python Developer at Codesky, Wrocław. B2B. Python, FastAPI, PostgreSQL. ' +
  'Apply by 15 December 2026: https://codesky.pl/careers/1'

const draft: JobOfferDraft = {
  title: 'Junior Python Developer',
  company_name: 'Codesky',
  location: 'Wrocław',
  experience_level: 'junior',
  employment_type: 'b2b',
  deadline: '2026-12-15',
  technologies: ['Python', 'FastAPI', 'PostgreSQL'],
  url: 'https://codesky.pl/careers/1',
  description: POSTING,
  parsed_with: 'ollama/qwen2.5:3b',
}

function renderPage() {
  render(
    <MemoryRouter>
      <NewOfferPage />
    </MemoryRouter>,
  )
}

// The description label also holds its hint, so it is matched by its start.
const field = (name: string | RegExp) => screen.getByLabelText(name) as HTMLInputElement
const fillButton = () => screen.getByRole('button', { name: 'Fill the form' })

function paste(text = POSTING) {
  fireEvent.change(screen.getByLabelText('Posting text'), { target: { value: text } })
}

beforeEach(() => {
  parse.mockReset()
  create.mockReset()
})
afterEach(cleanup)

describe('NewOfferPage paste box', () => {
  it('needs a posting long enough to read', () => {
    renderPage()
    expect(fillButton()).toHaveProperty('disabled', true)

    paste('Python dev')
    expect(fillButton()).toHaveProperty('disabled', true)

    paste()
    expect(fillButton()).toHaveProperty('disabled', false)
  })

  it('fills the form from the posting and saves nothing', async () => {
    parse.mockResolvedValue(draft)
    renderPage()

    paste()
    fireEvent.click(fillButton())

    await screen.findByText(/Filled by ollama\/qwen2.5:3b/)
    expect(parse).toHaveBeenCalledWith(POSTING)
    expect(field('Job title').value).toBe('Junior Python Developer')
    expect(field('Company').value).toBe('Codesky')
    expect(field('Location').value).toBe('Wrocław')
    expect(field('Link to the posting').value).toBe('https://codesky.pl/careers/1')
    expect(field('Deadline').value).toBe('2026-12-15')
    expect(field('Experience level').value).toBe('junior')
    expect(field('Employment type').value).toBe('b2b')
    expect(field(/^Description/).value).toBe(POSTING)
    expect(screen.getByText('FastAPI')).toBeTruthy()
    expect(create).not.toHaveBeenCalled()
  })

  it('names the fields the AI did not find', async () => {
    parse.mockResolvedValue({ ...draft, company_name: null, deadline: null })
    renderPage()

    paste()
    fireEvent.click(fillButton())

    expect(await screen.findByText(/Not found: company, deadline\./)).toBeTruthy()
    expect(field('Company').value).toBe('')
  })

  it('saves the checked fields only when Save offer is pressed', async () => {
    parse.mockResolvedValue(draft)
    create.mockResolvedValue({ id: 7 } as Awaited<ReturnType<typeof createJobOffer>>)
    renderPage()

    paste()
    fireEvent.click(fillButton())
    await screen.findByText(/Filled by/)
    fireEvent.change(field('Job title'), { target: { value: 'Python Developer' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save offer' }))

    await waitFor(() => expect(create).toHaveBeenCalledOnce())
    expect(create.mock.calls[0][0]).toMatchObject({
      title: 'Python Developer',
      company_name: 'Codesky',
      url: 'https://codesky.pl/careers/1',
      technologies: ['Python', 'FastAPI', 'PostgreSQL'],
      description: POSTING,
    })
  })

  it('shows a clear error when the AI is down and leaves the form as it was', async () => {
    parse.mockRejectedValue(new ApiError(502, "The AI provider didn't answer"))
    renderPage()
    fireEvent.change(field('Job title'), { target: { value: 'Typed title' } })

    paste()
    fireEvent.click(fillButton())

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain("The AI didn't answer")
    expect(field('Job title').value).toBe('Typed title')
    expect(field(/^Description/).value).toBe('')
    expect(fillButton()).toHaveProperty('disabled', false)
  })
})
