import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { mockAdmin } from '@/mocks/admin'

vi.mock('@/api/admin', () => ({ getAdminStats: () => Promise.resolve(mockAdmin.stats()) }))

import { AdminDashboardPage } from './AdminDashboardPage'

afterEach(cleanup)

describe('AdminDashboardPage', () => {
  it('shows the totals and both charts', async () => {
    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('match analyses')).toBeTruthy()
    expect(screen.getByText('hidden').previousSibling?.textContent).toBe('1')
    expect(screen.getByRole('img', { name: 'Searches per day, last 14 days' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'New accounts per week, last 8 weeks' })).toBeTruthy()
  })
})
