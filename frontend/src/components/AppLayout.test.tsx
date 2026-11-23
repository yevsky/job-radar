import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/features/auth/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, email: 'me@example.com' }, logout: vi.fn() }),
}))
vi.mock('@/lib/useIsAdmin', () => ({ useIsAdmin: () => false }))
vi.mock('@/lib/useDemoFeatures', () => ({ useDemoFeatures: () => [] }))
vi.mock('@/lib/theme', () => ({ useTheme: () => ['light', vi.fn()] }))

import { AppLayout } from './AppLayout'

function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppLayout />
    </MemoryRouter>,
  )
  return screen.getByTitle('Job board')
}

afterEach(cleanup)

describe('AppLayout', () => {
  it('marks Job board on the offers list and on one offer', () => {
    expect(show('/offers').className).toContain('active')
    cleanup()
    expect(show('/offers/12').getAttribute('aria-current')).toBe('page')
  })

  it('does not mark Job board on the Add an offer page', () => {
    const link = show('/offers/new')
    expect(link.className).not.toContain('active')
    expect(link.getAttribute('aria-current')).toBe('false')
  })
})
