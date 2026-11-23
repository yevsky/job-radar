/**
 * Shows the question asked with confirmAction() (lib/confirm.ts). Mounted once in App.
 * Esc, Cancel and a click outside the dialog all answer "no"; the yes button has the focus.
 */
import { useEffect, useRef } from 'react'

import { answerConfirm, useOpenConfirm } from '@/lib/confirm'

export function ConfirmHost() {
  const open = useOpenConfirm()
  const confirmRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const before = document.activeElement as HTMLElement | null
    confirmRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        answerConfirm(false)
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      before?.focus()
    }
  }, [open])

  if (!open) return null
  return (
    <div className="confirm-backdrop" onMouseDown={() => answerConfirm(false)}>
      <div
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby={open.message ? 'confirm-message' : undefined}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-title">{open.title}</h3>
        {open.message && (
          <div id="confirm-message" className="confirm-message">
            {open.message}
          </div>
        )}
        <div className="confirm-actions">
          <button type="button" className="btn" onClick={() => answerConfirm(false)}>
            {open.cancelLabel ?? 'Cancel'}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`btn ${open.danger ? 'btn-danger-solid' : 'btn-primary'}`}
            onClick={() => answerConfirm(true)}
          >
            {open.confirmLabel ?? 'OK'}
          </button>
        </div>
      </div>
    </div>
  )
}
