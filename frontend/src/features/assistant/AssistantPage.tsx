import { useEffect, useRef, useState, type FormEvent } from 'react'

import {
  MAX_MESSAGE_CHARS,
  MAX_TITLE_CHARS,
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  pendingActions,
  renameConversation,
  resolveAction,
  sendMessage,
  type ChatAction,
  type ChatMessage,
  type ConversationDetail,
} from '@/api/chat'
import { getProfile } from '@/api/profile'
import { Icon } from '@/components/Icon'
import { MatchDetails } from '@/features/match/MatchDetails'
import { DemoBadge, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { relativeDays } from '@/lib/format'
import { reloadTracked } from '@/lib/savedStore'
import { useAsync } from '@/lib/useAsync'

import { ActionCard } from './ActionCard'
import { Markdown } from './markdown'
import { PASTE_OFFER, suggestionsFor, type Suggestion } from './suggestions'

const LAST_KEY = 'jobradar.chat'

function readLast(): number | null {
  try {
    const value = Number(localStorage.getItem(LAST_KEY))
    return Number.isInteger(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

function rememberLast(id: number | null) {
  try {
    if (id === null) localStorage.removeItem(LAST_KEY)
    else localStorage.setItem(LAST_KEY, String(id))
  } catch {
    // only a convenience
  }
}

export function AssistantPage() {
  const list = useAsync(() => listConversations(), [])
  const [selected, setSelected] = useState<number | null>(readLast)
  const detail = useAsync(
    () => (selected === null ? Promise.resolve(null) : getConversation(selected)),
    [selected],
  )
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  // The message being answered, shown until the server's copy of it arrives
  const [waiting, setWaiting] = useState<Waiting | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [renaming, setRenaming] = useState<{ id: number; title: string } | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  // Suggestions written from the profile; without one (or if it fails) general ones
  const profile = useAsync(() => getProfile().catch(() => null), [])

  // A remembered conversation that is gone (deleted elsewhere): start fresh.
  useEffect(() => {
    if (detail.error && selected !== null) select(null)
  }, [detail.error, selected])

  // Only the selected conversation: while another one loads, the old one isn't shown
  const conversation = detail.data && detail.data.id === selected ? detail.data : null
  const messageCount = conversation?.messages.length ?? 0
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'end' })
  }, [messageCount, sending])

  function select(id: number | null) {
    setSelected(id)
    rememberLast(id)
    setError(null)
  }

  function update(id: number, change: (c: ConversationDetail) => ConversationDetail) {
    detail.setData((prev) => (prev && prev.id === id ? change(prev) : (prev ?? null)))
  }

  async function send(text: string) {
    const content = text.trim()
    if (!content || sending) return
    setSending(true)
    setError(null)
    setDraft('')
    try {
      let id = selected
      if (id === null) {
        const created = await createConversation()
        id = created.id
        detail.setData({ ...created, messages: [], actions: [] })
        select(id)
      }
      const known = new Set(conversation?.id === id ? conversation.messages.map((m) => m.id) : [])
      setWaiting({ conversationId: id, content, known })
      const reply = await sendMessage(id, content)
      const added = new Set(reply.messages.map((m) => m.id))
      update(id, (c) => ({
        ...c,
        title: c.title ?? content.slice(0, 80),
        // A reload while waiting may already hold some of the new rows
        messages: [...c.messages.filter((m) => !added.has(m.id)), ...reply.messages],
        actions: [
          ...c.actions.map((a) =>
            a.status === 'pending' ? { ...a, status: 'cancelled' as const } : a,
          ),
          ...reply.pending_actions,
        ],
      }))
      list.reload()
    } catch (err) {
      setDraft(content)
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setWaiting(null)
      setSending(false)
    }
  }

  async function resolve(action: ChatAction, verb: 'confirm' | 'cancel') {
    if (selected === null) return
    setError(null)
    try {
      const reply = await resolveAction(selected, action.id, verb)
      update(selected, (c) => ({
        ...c,
        messages: [...c.messages, reply.message],
        actions: c.actions.map((a) => (a.id === reply.action.id ? reply.action : a)),
      }))
      if (reply.action.status === 'confirmed' && reply.action.tool === 'save_offer') reloadTracked()
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
      detail.reload()
    }
  }

  async function resolveAll() {
    // One by one, so each change is checked again on its own and a failure doesn't stop the rest
    for (const action of pending) await resolve(action, 'confirm')
  }

  async function saveTitle() {
    if (!renaming) return
    const { id, title } = renaming
    setRenaming(null)
    const clean = title.trim()
    const old = list.data?.find((c) => c.id === id)?.title ?? null
    if (!clean || clean === old) return
    try {
      const saved = await renameConversation(id, clean)
      list.setData((rows) => (rows ?? []).map((c) => (c.id === id ? saved : c)))
      update(id, (c) => ({ ...c, title: saved.title }))
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    }
  }

  async function remove(id: number) {
    try {
      await deleteConversation(id)
      if (id === selected) select(null)
      list.reload()
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    }
  }

  function suggest(suggestion: Suggestion) {
    if (!suggestion.prefill) {
      void send(suggestion.text)
      return
    }
    setDraft(PASTE_OFFER)
    input.current?.focus()
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(draft)
  }

  const pending = conversation ? pendingActions(conversation.actions) : []
  const shown = conversation?.messages ?? []
  // The question shows at once; once the server has stored it, its own row takes over
  const question =
    waiting &&
    waiting.conversationId === selected &&
    !shown.some((m) => m.role === 'user' && !waiting.known.has(m.id))
      ? waiting.content
      : null
  const empty = shown.length === 0 && question === null

  return (
    <>
      <PageHeader
        icon="sparkle"
        title="AI assistant"
        lead="Ask about your applications, profile and CVs, or let it search for jobs. It reads on its own, but it saves or changes something only after you confirm."
        actions={<DemoBadge feature="assistant" />}
      />
      <div className="assistant">
        <aside className="assistant-list" aria-label="Conversations">
          <button className="btn btn-block" onClick={() => select(null)} disabled={sending}>
            <Icon name="plus" size={16} /> New chat
          </button>
          {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
          {list.data?.map((c) => (
            <div className="assistant-item" data-active={c.id === selected} key={c.id}>
              {renaming?.id === c.id ? (
                <input
                  className="input assistant-item-rename"
                  aria-label="Chat name"
                  autoFocus
                  value={renaming.title}
                  maxLength={MAX_TITLE_CHARS}
                  onChange={(e) => setRenaming({ id: c.id, title: e.target.value })}
                  onBlur={() => void saveTitle()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') e.currentTarget.blur()
                    if (e.key === 'Escape') setRenaming(null)
                  }}
                />
              ) : (
                <button className="assistant-item-open" onClick={() => select(c.id)}>
                  <span className="assistant-item-title">{c.title ?? 'New chat'}</span>
                  <span className="small faint">{relativeDays(c.updated_at)}</span>
                </button>
              )}
              <button
                className="btn btn-ghost btn-icon"
                aria-label={`Rename chat ${c.title ?? ''}`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => setRenaming({ id: c.id, title: c.title ?? '' })}
              >
                <Icon name="pencil" size={16} />
              </button>
              <button
                className="btn btn-ghost btn-icon"
                aria-label={`Delete chat ${c.title ?? ''}`}
                onClick={() => void remove(c.id)}
              >
                <Icon name="trash" size={16} />
              </button>
            </div>
          ))}
        </aside>

        <section className="assistant-chat card">
          <div className="assistant-messages" aria-live="polite">
            {detail.loading && selected !== null && !conversation && <Loading />}
            {empty && !sending && (
              <div className="assistant-welcome">
                <h2>What can I help with?</h2>
                <div className="assistant-suggestions">
                  {!profile.loading &&
                    suggestionsFor(profile.data ?? null).map((suggestion) => (
                      <button
                        key={suggestion.text}
                        className="pill"
                        onClick={() => suggest(suggestion)}
                      >
                        {suggestion.text}
                      </button>
                    ))}
                </div>
              </div>
            )}
            {shown.map((m) => (
              <MessageLine key={m.id} message={m} />
            ))}
            {question !== null && (
              <div className="assistant-bubble" data-role="user">
                {question}
              </div>
            )}
            {sending && (
              <div className="assistant-thinking">
                <span className="spinner" aria-hidden /> Thinking…
              </div>
            )}
            {!sending &&
              pending.map((action) => (
                <ActionCard
                  key={action.id}
                  action={action}
                  onConfirm={() => void resolve(action, 'confirm')}
                  onCancel={() => void resolve(action, 'cancel')}
                />
              ))}
            {!sending && pending.length > 1 && (
              <div className="row">
                <button className="btn btn-primary btn-sm" onClick={() => void resolveAll()}>
                  Confirm all {pending.length}
                </button>
              </div>
            )}
            <div ref={bottom} />
          </div>

          {error && <ErrorBox error={error} />}

          <form className="assistant-input" onSubmit={onSubmit}>
            <textarea
              ref={input}
              className="textarea"
              rows={2}
              value={draft}
              maxLength={MAX_MESSAGE_CHARS}
              placeholder="Ask anything about your job search…"
              aria-label="Message"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void send(draft)
                }
              }}
            />
            <button className="btn btn-primary" disabled={sending || !draft.trim()}>
              Send
            </button>
          </form>
        </section>
      </div>
    </>
  )
}

interface Waiting {
  conversationId: number
  content: string
  /** Rows the conversation had before this message */
  known: Set<number>
}

function MessageLine({ message }: { message: ChatMessage }) {
  if (message.role === 'tool') {
    return (
      <>
        <div className="assistant-tool">
          <Icon name="check" size={14} /> {message.content}
        </div>
        {message.analysis && (
          <section className="assistant-match card" aria-label="How you match">
            <MatchDetails a={message.analysis} />
          </section>
        )}
      </>
    )
  }
  return (
    <div className="assistant-bubble" data-role={message.role}>
      {message.role === 'assistant' ? <Markdown text={message.content} /> : message.content}
    </div>
  )
}
