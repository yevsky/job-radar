/** Helpers for the in-memory demo data. Demo data lives only in the browser tab. */
import { ApiError } from '@/api/client'

export const DAY = 86_400_000

/** ISO timestamp `days` from now (negative = past), at a fixed hour. */
export function daysFromNow(days: number, hour = 10): string {
  const d = new Date(Date.now() + days * DAY)
  d.setHours(hour, 0, 0, 0)
  return d.toISOString()
}

export function notFound(what: string): never {
  throw new ApiError(404, `${what} not found`)
}

let nextId = 1000
export const newId = () => nextId++
