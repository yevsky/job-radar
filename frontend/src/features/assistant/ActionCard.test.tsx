import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { pendingActions, type ChatAction } from '@/api/chat'

import { ActionCard } from './ActionCard'

const action: ChatAction = {
  id: 7,
  tool: 'set_application_status',
  summary: 'Move "Backend Developer" at Codesky from applied to interview',
  status: 'pending',
  result: null,
  created_at: '2026-11-22T20:00:00Z',
  resolved_at: null,
}

afterEach(cleanup)

describe('ActionCard', () => {
  it('shows what will change and waits for a button', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<ActionCard action={action} onConfirm={onConfirm} onCancel={onCancel} />)

    expect(screen.getByText(action.summary)).toBeTruthy()
    expect(onConfirm).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(onConfirm).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})

describe('pendingActions', () => {
  it('keeps only the actions still waiting', () => {
    const done = { ...action, id: 1, status: 'confirmed' as const }
    const second = { ...action, id: 8 }
    expect(pendingActions([done, action, second])).toEqual([action, second])
    expect(pendingActions([done])).toEqual([])
  })
})
