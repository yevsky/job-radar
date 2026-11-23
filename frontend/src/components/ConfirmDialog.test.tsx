import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { confirmAction } from '@/lib/confirm'

import { ConfirmHost } from './ConfirmDialog'

afterEach(cleanup)

function ask() {
  render(<ConfirmHost />)
  let answer: Promise<boolean> = Promise.resolve(false)
  act(() => {
    answer = confirmAction({
      title: 'Delete "QA"?',
      message: 'Applications that used this CV will show "Not recorded".',
      confirmLabel: 'Delete CV',
      danger: true,
    })
  })
  return answer
}

describe('ConfirmHost', () => {
  it('shows the question in the page and resolves true on the yes button', async () => {
    const answer = ask()
    expect(screen.getByRole('alertdialog').textContent).toContain('Delete "QA"?')
    fireEvent.click(screen.getByRole('button', { name: 'Delete CV' }))
    await expect(answer).resolves.toBe(true)
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('answers no on Cancel', async () => {
    const answer = ask()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await expect(answer).resolves.toBe(false)
  })

  it('answers no on Escape', async () => {
    const answer = ask()
    fireEvent.keyDown(window, { key: 'Escape' })
    await expect(answer).resolves.toBe(false)
  })

  it('puts the focus on the yes button', () => {
    void ask()
    expect(document.activeElement?.textContent).toBe('Delete CV')
  })
})
