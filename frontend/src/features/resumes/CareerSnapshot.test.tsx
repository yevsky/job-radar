import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Resume } from '@/api/resumes'

const makeInsights = vi.fn()
vi.mock('@/api/resumes', () => ({
  makeInsights: (id: number) => makeInsights(id) as unknown,
}))

import { CareerSnapshot } from './CareerSnapshot'

const resume: Resume = {
  id: 7,
  label: 'Backend CV',
  file_name: 'cv.pdf',
  created_at: '2026-11-20T10:00:00Z',
  extracted: {
    desired_position: 'Python developer',
    experience_level: 'junior',
    experience_years: 0.75,
    skills: ['Python'],
    locations: ['Wrocław', 'Remote'],
    employment_types: [],
    summary: null,
  },
  extracted_with: 'fake/fake',
  insights: {
    summary: 'I am a junior Python developer.',
    industries: ['Software engineering'],
    expertise: ['REST API development'],
    roles: ['Junior Backend Developer', 'Python Developer'],
    growth: ['Cloud platforms (AWS)'],
    advice: 'Look for junior backend roles.',
  },
  insights_with: 'fake/fake',
  applied_to_profile_at: null,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CareerSnapshot', () => {
  it('shows every part of the snapshot and the level code counted', () => {
    render(<CareerSnapshot resume={resume} />)

    expect(screen.getByText('I am a junior Python developer.')).toBeTruthy()
    expect(screen.getByText('Junior · 9 months of work')).toBeTruthy()
    expect(screen.getByText('Software engineering')).toBeTruthy()
    expect(screen.getByText('REST API development')).toBeTruthy()
    expect(screen.getByText(/Wrocław/)).toBeTruthy()
    expect(screen.getByText('Junior Backend Developer')).toBeTruthy()
    expect(screen.getByText('Cloud platforms (AWS)')).toBeTruthy()
    expect(screen.getByText('Look for junior backend roles.')).toBeTruthy()
    // no actions without handlers
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('hands a role to the profile form and shows the CV picker', () => {
    const onUseRole = vi.fn()
    render(
      <CareerSnapshot resume={resume} onUseRole={onUseRole} picker={<select aria-label="CV" />} />,
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Use Python Developer as desired position' }),
    )

    expect(onUseRole).toHaveBeenCalledWith('Python Developer')
    expect(screen.getByRole('combobox', { name: 'CV' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /use as bio/i })).toBeNull()
  })

  it('writes a missing snapshot on request', async () => {
    const onRegenerated = vi.fn()
    makeInsights.mockResolvedValue(resume)
    render(<CareerSnapshot resume={{ ...resume, insights: null }} onRegenerated={onRegenerated} />)

    expect(screen.getByText(/No snapshot yet/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /write snapshot/i }))

    expect(makeInsights).toHaveBeenCalledWith(7)
    await vi.waitFor(() => expect(onRegenerated).toHaveBeenCalledWith(resume))
  })
})
