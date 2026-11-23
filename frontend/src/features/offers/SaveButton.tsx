import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Icon } from '@/components/Icon'
import { statusColor, statusLabel } from '@/lib/labels'
import { toggleSaved, useTracked } from '@/lib/savedStore'

/**
 * Save / Saved for one offer. When the offer is already on the Applications board
 * (applied, interview, …), it shows that status and links to the board instead,
 * because unsaving would throw the application away.
 */
export function SaveButton({ offerId, compact = false }: { offerId: number; compact?: boolean }) {
  const tracked = useTracked()
  const [error, setError] = useState<string>()
  const current = tracked?.get(offerId)

  useEffect(() => {
    if (!error) return
    const timer = setTimeout(() => setError(undefined), 5000)
    return () => clearTimeout(timer)
  }, [error])

  if (current && current.status !== 'saved') {
    return (
      <Link
        to={`/applications?open=${current.applicationId}`}
        className={`btn ${compact ? 'btn-sm' : ''}`}
        title={`On your board as ${statusLabel[current.status]}. Open it there.`}
      >
        <span className="dot" style={{ background: statusColor(current.status) }} />
        {statusLabel[current.status]}
      </Link>
    )
  }

  const isSaved = current?.status === 'saved'
  return (
    <span className="save-button">
      <button
        type="button"
        className={`btn ${compact ? 'btn-sm' : ''}`}
        aria-pressed={isSaved}
        disabled={tracked === null}
        onClick={() => {
          setError(undefined)
          toggleSaved(offerId).catch((e: Error) => setError(e.message))
        }}
        title={isSaved ? 'Remove from My offers' : 'Keep it in My offers'}
      >
        <span style={{ color: isSaved ? 'var(--st-offer)' : undefined, display: 'inline-flex' }}>
          <Icon name="bookmark" size={16} />
        </span>
        {isSaved ? 'Saved' : 'Save'}
      </button>
      {error && (
        <span className="save-error" role="alert">
          {error}
        </span>
      )}
    </span>
  )
}
