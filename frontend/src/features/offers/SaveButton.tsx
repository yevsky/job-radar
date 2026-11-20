import { Icon } from '@/components/Icon'
import { toggleSaved, useSavedIds } from '@/lib/savedStore'

export function SaveButton({ offerId, compact = false }: { offerId: number; compact?: boolean }) {
  const saved = useSavedIds()
  const isSaved = saved?.has(offerId) ?? false
  const label = isSaved ? 'Saved' : 'Save'
  return (
    <button
      type="button"
      className={`btn ${compact ? 'btn-sm' : ''}`}
      aria-pressed={isSaved}
      disabled={saved === null}
      onClick={() => toggleSaved(offerId).catch((e: Error) => window.alert(e.message))}
      title={isSaved ? 'Remove from saved offers' : 'Save for later'}
    >
      <span style={{ color: isSaved ? 'var(--st-offer)' : undefined, display: 'inline-flex' }}>
        <Icon name="bookmark" size={16} />
      </span>
      {label}
    </button>
  )
}
