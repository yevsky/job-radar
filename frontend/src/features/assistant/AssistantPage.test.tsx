import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ChatReply, ConversationDetail } from '@/api/chat'

const api = vi.hoisted(() => ({
  listConversations: vi.fn(),
  createConversation: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
  renameConversation: vi.fn(),
  sendMessage: vi.fn(),
  resolveAction: vi.fn(),
}))

vi.mock('@/api/chat', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...api,
}))

import { AssistantPage } from './AssistantPage'

const empty: ConversationDetail = {
  id: 5,
  title: null,
  created_at: '2026-11-22T20:00:00Z',
  updated_at: '2026-11-22T20:00:00Z',
  messages: [],
  actions: [],
}

beforeEach(() => {
  localStorage.clear()
  api.listConversations.mockResolvedValue([])
  api.createConversation.mockResolvedValue({ ...empty })
  // The page reloads the new chat while the model is still answering: nothing stored yet
  api.getConversation.mockResolvedValue({ ...empty })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AssistantPage', () => {
  it('shows the first question of a new chat while waiting for the answer', async () => {
    let answer: (reply: ChatReply) => void = () => {}
    api.sendMessage.mockReturnValue(new Promise<ChatReply>((resolve) => (answer = resolve)))
    render(
      <MemoryRouter>
        <AssistantPage />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByText('How are my applications going?'))
    await waitFor(() => expect(api.getConversation).toHaveBeenCalledWith(5))
    await screen.findByText('Thinking…')
    expect(screen.getByText('How are my applications going?')).toBeTruthy()

    answer({
      messages: [
        {
          id: 1,
          role: 'user',
          content: 'How are my applications going?',
          tool_name: null,
          created_at: empty.created_at,
        },
        {
          id: 2,
          role: 'assistant',
          content: 'Three are in progress.',
          tool_name: null,
          created_at: empty.created_at,
        },
      ],
      pending_actions: [],
    })
    await screen.findByText('Three are in progress.')
    expect(screen.getAllByText('How are my applications going?')).toHaveLength(1)
  })

  it('renames a chat from the list', async () => {
    const row = { id: 7, title: 'Hi!', created_at: empty.created_at, updated_at: empty.updated_at }
    api.listConversations.mockResolvedValue([row])
    api.renameConversation.mockResolvedValue({ ...row, title: 'Python jobs' })
    render(
      <MemoryRouter>
        <AssistantPage />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Rename chat Hi!' }))
    const input = screen.getByRole('textbox', { name: 'Chat name' })
    fireEvent.change(input, { target: { value: '  Python jobs ' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    fireEvent.blur(input)

    await screen.findByText('Python jobs')
    expect(api.renameConversation).toHaveBeenCalledWith(7, 'Python jobs')
  })
})
