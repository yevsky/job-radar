import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'

const apps = [
  { id: 11, status: 'saved', job_offer: { id: 1 } },
  { id: 12, status: 'interview', job_offer: { id: 2 } },
  { id: 13, status: 'saved', job_offer: { id: 3 } },
]
const unsaveJob = vi.fn()
const saveJob = vi.fn()

vi.mock('@/api/applications', () => ({ listApplications: () => Promise.resolve(apps) }))
vi.mock('@/api/savedJobs', () => ({
  saveJob: (id: number) => saveJob(id) as unknown,
  unsaveJob: (id: number) => unsaveJob(id) as unknown,
}))

import { ConfirmHost } from '@/components/ConfirmDialog'

import { SaveButton } from './SaveButton'

function show(offerId: number) {
  render(
    <MemoryRouter>
      <SaveButton offerId={offerId} />
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SaveButton', () => {
  it('unsaves a saved offer', async () => {
    unsaveJob.mockResolvedValue(undefined)
    show(1)
    fireEvent.click(await screen.findByRole('button', { name: /saved/i }))
    expect(unsaveJob).toHaveBeenCalledWith(1)
    expect(await screen.findByRole('button', { name: /^save$/i })).toBeTruthy()
  })

  it('shows the status of an offer already on the board instead of a Saved it cannot undo', async () => {
    show(2)
    const link = await screen.findByRole('link', { name: /interview/i })
    expect(link.getAttribute('href')).toBe('/applications?open=12')
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('shows an error next to the button, not in a browser alert', async () => {
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})
    saveJob.mockRejectedValue(new ApiError(500, 'Server is down'))
    show(4)
    fireEvent.click(await screen.findByRole('button', { name: /^save$/i }))
    expect((await screen.findByRole('alert')).textContent).toBe('Server is down')
    expect(alert).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getByRole('button', { name: /^save$/i })).toBeTruthy())
  })

  it('treats "not saved" from the server as already gone, without an error', async () => {
    unsaveJob.mockRejectedValue(new ApiError(404, 'This offer is not saved'))
    show(3)
    fireEvent.click(await screen.findByRole('button', { name: /saved/i }))
    await waitFor(() => expect(unsaveJob).toHaveBeenCalledWith(3))
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('SaveButton on an offer only you can see', () => {
  function showPrivate(offerId: number, onDeleted: () => void) {
    render(
      <MemoryRouter>
        <ConfirmHost />
        <SaveButton offerId={offerId} isPrivate onDeleted={onDeleted} />
      </MemoryRouter>,
    )
  }

  it('asks first, then deletes it and tells the page', async () => {
    unsaveJob.mockResolvedValue(undefined)
    const onDeleted = vi.fn()
    showPrivate(1, onDeleted)
    fireEvent.click(await screen.findByRole('button', { name: /saved/i }))
    expect(await screen.findByText('Remove this offer?')).toBeTruthy()
    expect(unsaveJob).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(onDeleted).toHaveBeenCalled())
    expect(unsaveJob).toHaveBeenCalledWith(1)
  })

  it('keeps it when you cancel', async () => {
    const onDeleted = vi.fn()
    showPrivate(3, onDeleted)
    fireEvent.click(await screen.findByRole('button', { name: /saved/i }))
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByText('Remove this offer?')).toBeNull())
    expect(unsaveJob).not.toHaveBeenCalled()
    expect(onDeleted).not.toHaveBeenCalled()
  })
})
