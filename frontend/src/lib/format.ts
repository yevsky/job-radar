const dateFmt = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})
const shortFmt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const timeFmt = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })

export const formatDate = (iso: string | null | undefined) =>
  iso ? dateFmt.format(new Date(iso)) : ''
export const formatShort = (iso: string | Date) => shortFmt.format(new Date(iso))
export const formatTime = (iso: string) => timeFmt.format(new Date(iso))

/** "in 3 days", "2 days ago", "today". */
export function relativeDays(iso: string): string {
  const day = 86_400_000
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const diff = Math.round((startOf(new Date(iso)) - startOf(new Date())) / day)
  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  if (diff === -1) return 'yesterday'
  return diff > 0 ? `in ${diff} days` : `${-diff} days ago`
}

export function greeting(date = new Date()): string {
  const h = date.getHours()
  if (h < 5) return 'Good night'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export const pct = (part: number, whole: number) => (whole ? Math.round((part / whole) * 100) : 0)

/** YYYY-MM-DD in local time (calendar keys). */
export function dayKey(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export function initials(first?: string | null, last?: string | null, email?: string): string {
  const text = `${first?.[0] ?? ''}${last?.[0] ?? ''}`
  return (text || email?.[0] || '?').toUpperCase()
}
