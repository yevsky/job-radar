/**
 * Which offers the user saved, shared by every Save button on the page.
 * Loaded once per session; buttons update it optimistically.
 */
import { useEffect, useState } from 'react'

import { listSavedJobs, saveJob, unsaveJob } from '@/api/savedJobs'

let ids: Set<number> | null = null
let loading: Promise<void> | null = null
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

function load(): Promise<void> {
  loading ??= listSavedJobs()
    .then((saved) => {
      ids = new Set(saved.map((s) => s.job_offer.id))
      emit()
    })
    .catch(() => {
      loading = null
    })
  return loading
}

export function useSavedIds(): Set<number> | null {
  const [, force] = useState(0)
  useEffect(() => {
    const listener = () => force((n) => n + 1)
    listeners.add(listener)
    void load()
    return () => {
      listeners.delete(listener)
    }
  }, [])
  return ids
}

export async function toggleSaved(offerId: number): Promise<void> {
  const wasSaved = ids?.has(offerId) ?? false
  ids = new Set(ids)
  if (wasSaved) ids.delete(offerId)
  else ids.add(offerId)
  emit()
  try {
    if (wasSaved) await unsaveJob(offerId)
    else await saveJob(offerId)
  } catch (err) {
    ids = new Set(ids)
    if (wasSaved) ids.add(offerId)
    else ids.delete(offerId)
    emit()
    throw err
  }
}

/** An offer stopped being "saved" elsewhere (e.g. "I applied" moved it on the board). */
export function forgetSaved(offerId: number): void {
  if (!ids?.has(offerId)) return
  ids = new Set(ids)
  ids.delete(offerId)
  emit()
}

/** Save an offer (no toggle): used when a search result is kept, so it lands in Saved offers. */
export async function markSaved(offerId: number): Promise<void> {
  await saveJob(offerId) // 200 if it already has an application
  if (ids?.has(offerId)) return
  ids = new Set(ids)
  ids.add(offerId)
  emit()
}

/** Saved offers changed outside the Save buttons (the assistant saved one): load them again. */
export function reloadSaved(): void {
  loading = null
  void load()
}
