import type { ApplicationStats, StatsRange } from '@/api/applications'
import { dayKey } from '@/lib/format'

type Week = ApplicationStats['weekly'][number]

const WEEK = 7 * 86_400_000

/** Monday of the week `date` is in, as YYYY-MM-DD. */
export function mondayKey(date: Date): string {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return dayKey(d)
}

/**
 * "All time" starts at your first activity, so a new account has one lonely week. Pad it with
 * empty weeks in front so the chart always shows at least `min` weeks. The 30 and 90 day ranges
 * already cover a fixed window and stay as they are.
 */
export function padWeeks(weekly: Week[], range: StatsRange, min = 13, today = new Date()): Week[] {
  if (range !== 'all' || weekly.length >= min) return weekly
  const first = weekly[0]?.week_start ?? mondayKey(today)
  const padded = [...weekly]
  if (padded.length === 0) padded.push({ week_start: first, saved: 0, applied: 0, replied: 0 })
  let start = new Date(`${first}T12:00:00`).getTime()
  while (padded.length < min) {
    start -= WEEK
    padded.unshift({ week_start: dayKey(new Date(start)), saved: 0, applied: 0, replied: 0 })
  }
  return padded
}

/** Weeks in a row with at least one application, counting back from now. */
export function applyStreak(weekly: Week[]): number {
  let i = weekly.length - 1
  // The current week may simply not have had its application yet.
  if (i >= 0 && weekly[i].applied === 0) i -= 1
  let streak = 0
  while (i >= 0 && weekly[i].applied > 0) {
    streak += 1
    i -= 1
  }
  return streak
}
