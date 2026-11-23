import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SourceSwitch } from '@/api/admin'

const rows: SourceSwitch[] = [
  { name: 'tavily', enabled: true, ok: null, features: [], updated_at: null },
  { name: 'jsearch', enabled: true, ok: null, features: ['country'], updated_at: null },
]
const switchSource = vi.fn((name: string, enabled: boolean) =>
  Promise.resolve({
    ...rows.find((r) => r.name === name)!,
    enabled,
    updated_at: '2026-11-23T12:00:00Z',
  }),
)

vi.mock('@/api/admin', () => ({
  listSourceSwitches: () => Promise.resolve(rows),
  switchSource: (name: string, enabled: boolean) => switchSource(name, enabled),
}))

import { AdminSourcesPage } from './AdminSourcesPage'

afterEach(cleanup)

describe('AdminSourcesPage', () => {
  it('switches a source off for everyone', async () => {
    render(<AdminSourcesPage />)

    const toggle = await screen.findByLabelText('JSearch (Google Jobs) for all users')
    fireEvent.click(toggle)

    await waitFor(() => expect(switchSource).toHaveBeenCalledWith('jsearch', false))
    expect(await screen.findByText('Off for everyone')).toBeTruthy()
    expect(screen.getByText('On for everyone')).toBeTruthy() // Tavily is still on
  })
})
