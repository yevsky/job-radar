/**
 * Which offers the user tracks, and where each one is: `saved`, or further on the board
 * (applied, interview, …). Shared by every Save button on the page.
 *
 * It is loaded from GET /applications when the first button of a page appears, and again on
 * the next page, so a status changed on the Applications board shows up here too. Buttons
 * update it optimistically.
 *
 * Only `saved` can be undone with the Save button. An offer that is already on the board
 * (e.g. applied) shows its status instead, because "unsaving" it would delete an application.
 */
import { useEffect, useState } from 'react'

import { listApplications } from '@/api/applications'
import { ApiError } from '@/api/client'
import type { ApplicationStatus } from '@/api/enums'
import { saveJob, unsaveJob } from '@/api/savedJobs'

export interface Tracked {
  applicationId: number
  status: ApplicationStatus
}

let tracked: Map<number, Tracked> | null = null
let loading: Promise<void> | null = null
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

function load(): Promise<void> {
  loading ??= listApplications()
    .then((apps) => {
      tracked = new Map(
        apps.map((a) => [a.job_offer.id, { applicationId: a.id, status: a.status }]),
      )
      emit()
    })
    .catch(() => {
      loading = null
    })
  return loading
}

function set(offerId: number, value: Tracked | null): void {
  tracked = new Map(tracked)
  if (value) tracked.set(offerId, value)
  else tracked.delete(offerId)
  emit()
}

/** offer id -> its application; null until loaded. */
export function useTracked(): Map<number, Tracked> | null {
  const [, force] = useState(0)
  useEffect(() => {
    const listener = () => force((n) => n + 1)
    listeners.add(listener)
    void load()
    return () => {
      listeners.delete(listener)
      // the last button left the page: load again on the next page
      if (listeners.size === 0) loading = null
    }
  }, [])
  return tracked
}

/** Save an offer, or unsave one that is only saved. */
export async function toggleSaved(offerId: number): Promise<void> {
  const before = tracked?.get(offerId) ?? null
  if (before && before.status !== 'saved') return // on the board: not the Save button's job
  try {
    if (before) {
      set(offerId, null)
      await unsaveJob(offerId)
    } else {
      set(offerId, { applicationId: 0, status: 'saved' })
      const saved = await saveJob(offerId)
      set(offerId, { applicationId: saved.id, status: saved.status })
    }
  } catch (err) {
    if (before && err instanceof ApiError && err.status === 404) {
      // Not saved any more (removed or moved on in another tab): show what the server has.
      reloadTracked()
      return
    }
    set(offerId, before)
    throw err
  }
}

/** The offer's application changed elsewhere (e.g. "I applied" on the offer page). */
export function setTracked(offerId: number, value: Tracked | null): void {
  set(offerId, value)
}

/** Save an offer (no toggle): used when a search result is kept, so it lands in My offers. */
export async function markSaved(offerId: number): Promise<void> {
  const saved = await saveJob(offerId) // 200 if it already has an application
  set(offerId, { applicationId: saved.id, status: saved.status })
}

/** Applications changed outside the Save buttons (the assistant saved one): load them again. */
export function reloadTracked(): void {
  loading = null
  void load()
}
