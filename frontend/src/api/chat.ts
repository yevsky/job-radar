/**
 * The AI assistant (milestone 11). Conversations are stored by the backend; a change the
 * assistant asks for (save an offer, change a status) waits as a pending action until the
 * user confirms or cancels it. One message can ask for several changes.
 *
 *   GET    /chat                                   -> Conversation[] (newest first)
 *   POST   /chat                                   -> Conversation (201)
 *   GET    /chat/{id}                              -> ConversationDetail
 *   DELETE /chat/{id}                              -> 204
 *   POST   /chat/{id}/messages {content}           -> ChatReply
 *   POST   /chat/{id}/actions/{action}/confirm     -> ActionReply
 *   POST   /chat/{id}/actions/{action}/cancel      -> ActionReply
 */
import { planned, request } from './client'
import type { MatchView } from '@/features/match/MatchDetails'
import { mockChat } from '@/mocks/chat'

export interface Conversation {
  id: number
  title: string | null
  created_at: string
  updated_at: string
}

/** `tool` rows are the grey "Searched jobs: 8 results" lines between messages. */
export type ChatRole = 'user' | 'assistant' | 'tool'

export interface ChatMessage {
  id: number
  role: ChatRole
  content: string
  tool_name: string | null
  created_at: string
  /** analyse_offer rows: the match card, as on the offer page. */
  analysis?: MatchView | null
}

export type ActionStatus = 'pending' | 'confirmed' | 'cancelled' | 'failed'

export interface ChatAction {
  id: number
  tool: string
  summary: string
  status: ActionStatus
  result: string | null
  created_at: string
  resolved_at: string | null
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[]
  actions: ChatAction[]
}

export interface ChatReply {
  /** The rows the message added, the user's own message first. */
  messages: ChatMessage[]
  /** One per change the assistant asked for ("move both" makes two). */
  pending_actions: ChatAction[]
}

export interface ActionReply {
  action: ChatAction
  message: ChatMessage
}

export const MAX_MESSAGE_CHARS = 12000 // room for a pasted job posting
export const MAX_TITLE_CHARS = 80

const FEATURE = 'assistant'

export const listConversations = () =>
  planned(
    FEATURE,
    () => request<Conversation[]>('/chat'),
    () => mockChat.list(),
  )

export const createConversation = () =>
  planned(
    FEATURE,
    () => request<Conversation>('/chat', { method: 'POST' }),
    () => mockChat.create(),
  )

export const getConversation = (id: number) =>
  planned(
    FEATURE,
    () => request<ConversationDetail>(`/chat/${id}`),
    () => mockChat.get(id),
  )

export const renameConversation = (id: number, title: string) =>
  planned(
    FEATURE,
    () => request<Conversation>(`/chat/${id}`, { method: 'PATCH', body: { title } }),
    () => mockChat.rename(id, title),
  )

export const deleteConversation = (id: number) =>
  planned(
    FEATURE,
    () => request<void>(`/chat/${id}`, { method: 'DELETE' }),
    () => mockChat.remove(id),
  )

export const sendMessage = (id: number, content: string) =>
  planned(
    FEATURE,
    () => request<ChatReply>(`/chat/${id}/messages`, { method: 'POST', body: { content } }),
    () => mockChat.send(id, content),
  )

export const resolveAction = (id: number, actionId: number, verb: 'confirm' | 'cancel') =>
  planned(
    FEATURE,
    () => request<ActionReply>(`/chat/${id}/actions/${actionId}/${verb}`, { method: 'POST' }),
    () => mockChat.resolve(id, actionId, verb),
  )

/** The actions still waiting for the user. */
export function pendingActions(actions: ChatAction[]): ChatAction[] {
  return actions.filter((a) => a.status === 'pending')
}
