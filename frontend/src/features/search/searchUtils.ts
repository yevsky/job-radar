import type { SearchResult, SearchSources, SourceFeature } from '@/api/search'

export type SortKey = 'relevant' | 'salary' | 'newest'

const DAY = 86_400_000
const grouped = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
/** 12 000 style grouping (narrow no-break space), also for 4-digit numbers. */
const money = { format: (n: number) => grouped.format(n).replace(/,/g, '\u202f') }
const PERIOD = { hour: 'h', month: 'month', year: 'year' } as const

/** "100–130 PLN / h", or null when the source gave no salary. */
export function formatSalary(r: SearchResult): string | null {
  if (!r.salary_min && !r.salary_max) return null
  const range =
    r.salary_min && r.salary_max && r.salary_min !== r.salary_max
      ? `${money.format(r.salary_min)}–${money.format(r.salary_max)}`
      : money.format((r.salary_max ?? r.salary_min)!)
  const period = r.salary_period ? ` / ${PERIOD[r.salary_period]}` : ''
  return `${range} ${r.salary_currency ?? ''}${period}`.replace(/\s+/g, ' ').trim()
}

/** Monthly equivalent, only for sorting (160 h per month, 12 months per year). */
function monthly(r: SearchResult): number {
  const top = r.salary_max ?? r.salary_min ?? 0
  if (r.salary_period === 'hour') return top * 160
  if (r.salary_period === 'year') return top / 12
  return top
}

export function sortResults(results: SearchResult[], key: SortKey): SearchResult[] {
  if (key === 'relevant') return results
  const copy = [...results]
  if (key === 'salary') return copy.sort((a, b) => monthly(b) - monthly(a))
  return copy.sort((a, b) => (b.posted_at ?? '').localeCompare(a.posted_at ?? ''))
}

export function isNew(r: SearchResult, now: number): boolean {
  return !!r.posted_at && now - new Date(r.posted_at).getTime() < 3 * DAY
}

export function isRemote(r: SearchResult): boolean {
  return (r.location ?? '').toLowerCase().includes('remote')
}

/** Two letters for the company tile. */
export function monogram(company: string): string {
  const words = company
    .replace(/[^\p{L}\p{N} ]/gu, '')
    .split(/\s+/)
    .filter(Boolean)
  return ((words[0]?.[0] ?? '') + (words[1]?.[0] ?? words[0]?.[1] ?? '')).toUpperCase()
}

/** Stable tile colour per company, from the status palette. */
const TILE_COLORS = ['applied', 'screening', 'interview', 'offer', 'accepted', 'rejected']
export function tileColor(company: string): string {
  let hash = 0
  for (const ch of company) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return `var(--st-${TILE_COLORS[hash % TILE_COLORS.length]})`
}

/** Other results ranked by shared technologies, then same level. */
export function similarTo(target: SearchResult, all: SearchResult[]): SearchResult[] {
  const techs = new Set((target.technologies ?? []).map((t) => t.toLowerCase()))
  return all
    .filter((r) => r.url !== target.url)
    .map((r) => ({
      r,
      score:
        (r.technologies ?? []).filter((t) => techs.has(t.toLowerCase())).length * 2 +
        (r.experience_level === target.experience_level ? 1 : 0),
    }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
    .map((x) => x.r)
}

/** The sources a search asks: the user's choice, or every available one. */
export function activeSources(data: SearchSources): string[] {
  const { available, chosen } = data
  const picked = chosen ? chosen.filter((s) => available.includes(s)) : []
  return picked.length > 0 ? picked : available
}

/** True if at least one of the active sources uses this form field. */
export function supports(data: SearchSources | undefined, feature: SourceFeature): boolean {
  if (!data?.features) return true // an older backend sends no features: allow everything
  return activeSources(data).some((s) => data.features?.[s]?.includes(feature))
}
