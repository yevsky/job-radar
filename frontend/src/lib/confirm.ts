/**
 * The site's own "Are you sure?" question, instead of the browser's window.confirm().
 *
 *   if (!(await confirmAction({ title: 'Delete this CV?', confirmLabel: 'Delete', danger: true })))
 *     return
 *
 * <ConfirmHost /> (components/ConfirmDialog.tsx) is mounted once in App and shows it.
 */
import { useEffect, useState, type ReactNode } from 'react'

export interface ConfirmOptions {
  title: string
  /** More detail under the title. */
  message?: ReactNode
  /** Text of the button that says yes, e.g. 'Delete'. */
  confirmLabel?: string
  cancelLabel?: string
  /** Red button: for deleting or anything that can't be undone. */
  danger?: boolean
}

interface Open extends ConfirmOptions {
  resolve: (yes: boolean) => void
}

let current: Open | null = null
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

/** Ask the user; resolves true when they confirm. */
export function confirmAction(options: ConfirmOptions): Promise<boolean> {
  current?.resolve(false) // a newer question replaces an open one
  return new Promise((resolve) => {
    current = { ...options, resolve }
    emit()
  })
}

/** The user answered (or closed the dialog: false). */
export function answerConfirm(yes: boolean) {
  const open = current
  current = null
  emit()
  open?.resolve(yes)
}

/** The open question, or null; re-renders when it changes. */
export function useOpenConfirm(): Readonly<ConfirmOptions> | null {
  const [, force] = useState(0)
  useEffect(() => {
    const listener = () => force((n) => n + 1)
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [])
  return current
}
