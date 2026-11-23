/**
 * A very small Markdown reader for the assistant's answers: **bold**, [links](https://...) and
 * "- " / "1. " list lines. It builds React elements (never HTML strings), so text from the model
 * can't inject markup. Anything else stays plain text.
 */
import type { ReactNode } from 'react'

const INLINE = /\*\*(.+?)\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    const at = match.index
    if (at > last) parts.push(text.slice(last, at))
    if (match[1] !== undefined) {
      parts.push(<strong key={at}>{match[1]}</strong>)
    } else {
      parts.push(
        <a key={at} href={match[3]} target="_blank" rel="noreferrer">
          {match[2]}
        </a>,
      )
    }
    last = at + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

const LIST_ITEM = /^\s*(?:[-*]|\d+\.)\s+/

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let items: string[] = []
  const flush = (key: number) => {
    if (items.length) {
      blocks.push(
        <ul key={`l${key}`}>
          {items.map((item, i) => (
            <li key={i}>{inline(item)}</li>
          ))}
        </ul>,
      )
      items = []
    }
  }
  text.split('\n').forEach((line, i) => {
    if (LIST_ITEM.test(line)) {
      items.push(line.replace(LIST_ITEM, ''))
      return
    }
    flush(i)
    if (line.trim()) blocks.push(<p key={i}>{inline(line)}</p>)
  })
  flush(-1)
  return <>{blocks}</>
}
