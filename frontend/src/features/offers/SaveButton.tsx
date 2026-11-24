import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Icon } from '@/components/Icon'
import { confirmAction } from '@/lib/confirm'
import { statusColor, statusLabel } from '@/lib/labels'
import { toggleSaved, useTracked } from '@/lib/savedStore'

/**
 * Save / Saved for one offer. When the offer is already on the Applications board
 * (applied, interview, …), it shows that status and links to the board instead,
 * because unsaving would throw the application away.
 *
 * An offer only you can see (`isPrivate`: added by you or kept from a search) is deleted
 * by the server when you unsave it, with its match analysis and summary, so the button
 * asks first and then calls `onDeleted`.
 */
export function SaveButton({
  offerId,
  compact = false,
  isPrivate = false,
  onDeleted,
}: {
  offerId: number
  compact?: boolean
  isPrivate?: boolean
  onDeleted?: () => void
}) {
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
  const deletes = isSaved && isPrivate

  async function toggle() {
    setError(undefined)
    if (
      deletes &&
      !(await confirmAction({
        title: 'Remove this offer?',
        message:
          'Only you can see it, so removing it from My offers deletes it for good, with its match analysis and summary.',
        confirmLabel: 'Remove',
        danger: true,
      }))
    )
      return
    try {
      await toggleSaved(offerId)
      if (deletes) onDeleted?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    }
  }
  return (
    <span className="save-button">
      <button
        type="button"
        className={`btn ${compact ? 'btn-sm' : ''}`}
        aria-pressed={isSaved}
        disabled={tracked === null}
        onClick={() => void toggle()}
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
