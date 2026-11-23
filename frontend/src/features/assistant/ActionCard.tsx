import type { ChatAction } from '@/api/chat'
import { Icon } from '@/components/Icon'

/** A change the assistant asked for. Nothing happens until the user presses Confirm. */
export function ActionCard({
  action,
  onConfirm,
  onCancel,
}: {
  action: ChatAction
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="assistant-action" role="group" aria-label="Change waiting for your OK">
      <div className="row" style={{ gap: 8 }}>
        <Icon name="alert" size={16} />
        <strong>Waiting for your OK</strong>
      </div>
      <p>{action.summary}</p>
      <div className="row">
        <button className="btn btn-primary btn-sm" onClick={onConfirm}>
          Confirm
        </button>
        <button className="btn btn-sm" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}
