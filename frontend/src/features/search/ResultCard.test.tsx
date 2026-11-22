import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SearchResult } from '@/api/search'

import { ResultCard } from './ResultCard'

const result: SearchResult = {
  title: 'Junior Python Developer',
  company_name: 'Codesky',
  url: 'https://example.com/1',
  location: 'Katowice',
  experience_level: 'junior',
  technologies: ['Python', 'FastAPI'],
  found_via: 'tavily',
}

function renderCard(props: Partial<Parameters<typeof ResultCard>[0]> = {}) {
  const onOpen = vi.fn()
  const onSave = vi.fn()
  render(
    <ResultCard
      result={result}
      selected={false}
      compact={false}
      savedId={undefined}
      now={Date.now()}
      onOpen={onOpen}
      onSave={onSave}
      {...props}
    />,
  )
  return { onOpen, onSave }
}

afterEach(cleanup)

describe('ResultCard', () => {
  it('shows the offer', () => {
    renderCard()
    expect(screen.getByRole('heading', { name: 'Junior Python Developer' })).toBeTruthy()
    expect(screen.getByText('Codesky')).toBeTruthy()
    expect(screen.getByText('Katowice')).toBeTruthy()
    expect(screen.getByText('FastAPI')).toBeTruthy()
  })

  it('shows why a hidden result was left out', () => {
    renderCard({ hiddenBecause: 'other_city' })
    expect(screen.getByText('other city')).toBeTruthy()
  })

  it('has no reason tag for a found result', () => {
    renderCard()
    expect(screen.queryByText('other city')).toBeNull()
  })

  it('saves without opening the offer', () => {
    const { onOpen, onSave } = renderCard()
    fireEvent.click(screen.getByRole('button', { name: 'Save to my offers' }))
    expect(onSave).toHaveBeenCalledOnce()
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('does not save twice', () => {
    const { onSave } = renderCard({ savedId: 7 })
    fireEvent.click(screen.getByRole('button', { name: 'Saved to my offers' }))
    expect(onSave).not.toHaveBeenCalled()
  })

  it('opens on click', () => {
    const { onOpen } = renderCard()
    fireEvent.click(screen.getByRole('article'))
    expect(onOpen).toHaveBeenCalledOnce()
  })
})
