/** Demo assistant for mock mode: canned answers that show the tool lines and a confirm card. */
import type {
  ActionReply,
  ChatAction,
  ChatMessage,
  ChatReply,
  Conversation,
  ConversationDetail,
} from '@/api/chat'

import { newId, notFound } from './util'

const conversations: ConversationDetail[] = []

const now = () => new Date().toISOString()

function row(
  role: ChatMessage['role'],
  content: string,
  tool_name: string | null = null,
): ChatMessage {
  return { id: newId(), role, content, tool_name, created_at: now() }
}

function find(id: number): ConversationDetail {
  return conversations.find((c) => c.id === id) ?? notFound('Conversation')
}

function summary(c: ConversationDetail): Conversation {
  return { id: c.id, title: c.title, created_at: c.created_at, updated_at: c.updated_at }
}

export const mockChat = {
  list: (): Conversation[] =>
    [...conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(summary),

  create: (): Conversation => {
    const c: ConversationDetail = {
      id: newId(),
      title: null,
      created_at: now(),
      updated_at: now(),
      messages: [],
      actions: [],
    }
    conversations.push(c)
    return summary(c)
  },

  get: (id: number): ConversationDetail => structuredClone(find(id)),

  rename: (id: number, title: string): Conversation => {
    const c = find(id)
    c.title = title
    return summary(c)
  },

  remove: (id: number): void => {
    conversations.splice(conversations.indexOf(find(id)), 1)
  },

  send: (id: number, content: string): ChatReply => {
    const c = find(id)
    c.actions.forEach((a) => {
      if (a.status === 'pending') a.status = 'cancelled'
    })
    c.title ??= content.slice(0, 80)
    const added = [row('user', content)]
    let pending: ChatAction | null = null
    if (/analy|match/i.test(content)) {
      added.push({
        ...row('tool', 'Analysed the match: 74/100', 'analyse_offer'),
        analysis: {
          score: 74,
          summary: 'A junior Python role close to what you want; PostgreSQL is new to you.',
          reasons: ['Python and FastAPI are your main skills'],
          red_flags: ['Unpaid 2-week trial'],
          matched_skills: ['Python', 'FastAPI'],
          missing_skills: ['PostgreSQL'],
          provider: 'demo',
          model: 'demo',
          prompt_version: 'offer-analysis-v3',
        },
      })
      added.push(
        row(
          'assistant',
          'A good match (74/100): your Python and FastAPI fit, PostgreSQL is new to you. Do you want me to save it?',
        ),
      )
    } else if (/save/i.test(content)) {
      added.push(row('tool', 'Prepared a change for you to confirm', 'save_offer'))
      pending = {
        id: newId(),
        tool: 'save_offer',
        summary: 'Save "Junior Python Developer" at Codesky to your saved offers',
        status: 'pending',
        result: null,
        created_at: now(),
        resolved_at: null,
      }
      c.actions.push(pending)
      added.push(row('assistant', 'Please confirm or cancel the change below.'))
    } else {
      added.push(row('tool', 'Read your applications: 4', 'list_applications'))
      added.push(
        row(
          'assistant',
          'This is the demo assistant. With the backend running, I can search jobs, read your profile, CVs and applications, and save offers or change statuses after you confirm.',
        ),
      )
    }
    c.messages.push(...added)
    c.updated_at = now()
    return { messages: added, pending_actions: pending ? [pending] : [] }
  },

  resolve: (id: number, actionId: number, verb: 'confirm' | 'cancel'): ActionReply => {
    const c = find(id)
    const action = c.actions.find((a) => a.id === actionId) ?? notFound('Action')
    action.status = verb === 'confirm' ? 'confirmed' : 'cancelled'
    action.resolved_at = now()
    const message = row(
      'assistant',
      verb === 'confirm'
        ? 'Done: Saved "Junior Python Developer" at Codesky.'
        : `Cancelled: ${action.summary}.`,
    )
    c.messages.push(message)
    return { action: { ...action }, message }
  },
}
