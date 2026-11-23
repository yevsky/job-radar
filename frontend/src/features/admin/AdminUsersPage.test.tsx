import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AdminUser } from '@/api/admin'

const users: AdminUser[] = [
  {
    id: 1,
    email: 'me@example.com',
    role_id: 2,
    role: 'admin',
    created_at: '2026-11-01T10:00:00Z',
    search_daily_limit: null,
  },
  {
    id: 2,
    email: 'ola@example.com',
    role_id: 1,
    role: 'user',
    created_at: '2026-11-02T10:00:00Z',
    search_daily_limit: 25,
  },
]
const setRole = vi.fn((id: number, role: 'user' | 'admin') =>
  Promise.resolve({ ...users[1], id, role }),
)

vi.mock('@/api/admin', () => ({
  listUsers: () => Promise.resolve(users),
  setRole: (id: number, role: 'user' | 'admin') => setRole(id, role),
  setSearchLimit: vi.fn(),
  deleteUser: vi.fn(),
}))
vi.mock('@/features/auth/AuthContext', () => ({
  useAuth: () => ({ user: users[0] }),
}))

import { AdminUsersPage } from './AdminUsersPage'

afterEach(cleanup)

describe('AdminUsersPage', () => {
  it("doesn't let you change your own role or delete yourself", async () => {
    render(<AdminUsersPage />)

    const own = await screen.findByLabelText('Role of me@example.com')
    expect((own as HTMLSelectElement).disabled).toBe(true)
    expect(screen.queryByLabelText('Delete me@example.com')).toBeNull()
    expect(screen.getByLabelText('Delete ola@example.com')).toBeTruthy()
  })

  it('saves a new role for another user', async () => {
    render(<AdminUsersPage />)

    const select = await screen.findByLabelText('Role of ola@example.com')
    fireEvent.change(select, { target: { value: 'admin' } })

    await waitFor(() => expect(setRole).toHaveBeenCalledWith(2, 'admin'))
    expect(await screen.findByText('Saved')).toBeTruthy()
  })

  it('filters the list by email', async () => {
    render(<AdminUsersPage />)

    fireEvent.change(await screen.findByLabelText('Find a user by email'), {
      target: { value: 'ola' },
    })

    expect(screen.queryByText('me@example.com')).toBeNull()
    expect(screen.getByText('1 of 2 accounts')).toBeTruthy()
  })
})
