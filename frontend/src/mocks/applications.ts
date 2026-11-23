/**
 * Demo applications with a status history, plus the stats and calendar the backend will
 * compute in milestone 9. The logic here doubles as a reference for the backend service.
 */
import type {
  Application,
  ApplicationCreate,
  ApplicationStats,
  StaleStage,
  ApplicationUpdate,
  CalendarEvent,
  StatsRange,
  StatusChange,
} from '@/api/applications'
import { FUNNEL_STAGES, type ApplicationStatus, type FunnelStage } from '@/api/enums'
import { dayKey } from '@/lib/format'

import type { JobOfferListItem } from '@/api/jobOffers'
import { API_MODE } from '@/api/config'

import { mockOffers, toListItem } from './offers'
import { DAY, daysFromNow, newId, notFound } from './util'

interface Row extends Application {
  history: StatusChange[]
}

/** [offer id, [status, days ago]...], interview in N days (optional). */
const seeds: [number, [ApplicationStatus, number][], number?][] = [
  [
    1,
    [
      ['applied', 62],
      ['screening', 55],
      ['interview', 48],
      ['offer', 40],
      ['declined', 36],
    ],
  ],
  [
    2,
    [
      ['applied', 58],
      ['screening', 50],
      ['rejected', 47],
    ],
  ],
  [
    3,
    [
      ['applied', 51],
      ['rejected', 44],
    ],
  ],
  [
    5,
    [
      ['applied', 44],
      ['screening', 39],
      ['interview', 30],
      ['offer', 9],
    ],
  ],
  [6, [['applied', 37]]],
  [
    8,
    [
      ['applied', 30],
      ['screening', 24],
      ['interview', 12],
    ],
    3,
  ],
  [
    9,
    [
      ['applied', 23],
      ['screening', 18],
    ],
  ],
  [
    11,
    [
      ['applied', 16],
      ['screening', 12],
      ['interview', 6],
      ['rejected', 2],
    ],
  ],
  [2, [['applied', 9]]],
  [
    7,
    [
      ['saved', 6],
      ['applied', 4],
      ['screening', 1],
    ],
    6,
  ],
  [
    12,
    [
      ['saved', 16],
      ['applied', 2],
    ],
  ],
  // Saved, not applied yet: these show on the Saved offers page and in the Saved column.
  [4, [['saved', 1]]],
  [10, [['saved', 9]]],
]

/** Same rules as the backend: stale after this many days in one status. */
const STALE_RULES: [StaleStage['stage'], number][] = [
  ['saved', 7],
  ['applied', 10],
  ['screening', 10],
  ['interview', 7],
  ['offer', 3],
]

const REPLY_STATUSES: ApplicationStatus[] = [
  'screening',
  'interview',
  'offer',
  'accepted',
  'rejected',
]

/** When the company first answered (good or bad), or null if it hasn't. */
function firstReplyAt(r: Row): string | null {
  if (!r.applied_at) return null
  const applied = r.applied_at
  return (
    r.history.find((h) => REPLY_STATUSES.includes(h.status) && h.changed_at >= applied)
      ?.changed_at ?? null
  )
}

const seeded = (): Row[] =>
  seeds.map(([offerId, steps, interviewIn], index) => {
    const history = steps.map(([status, ago]) => ({
      status,
      changed_at: daysFromNow(-ago, 9 + (index % 6)),
    }))
    const last = history[history.length - 1]
    const interviewStep = history.find((h) => h.status === 'interview')
    return {
      id: index + 1,
      job_offer: toListItem(mockOffers.get(offerId)),
      status: last.status,
      resume_id: index % 3 === 0 ? 2 : 1,
      notes: index === 3 ? 'Recruiter: Marta. Second round was a system design chat.' : null,
      applied_at: history.find((h) => h.status !== 'saved')?.changed_at ?? null,
      interview_at:
        interviewIn !== undefined
          ? daysFromNow(interviewIn, 14)
          : interviewStep
            ? interviewStep.changed_at
            : null,
      created_at: history[0].changed_at,
      updated_at: last.changed_at,
      history,
    }
  })

/**
 * With a real backend (auto mode) the board starts empty and works on your real offers; what you
 * do is kept in this browser until the applications endpoints exist. Mock mode uses the seeds.
 */
const STORE_KEY = 'jobradar.demo.applications'
const persistent = API_MODE !== 'mock'

function load(): Row[] {
  if (!persistent) return seeded()
  try {
    const raw = localStorage.getItem(STORE_KEY)
    return raw ? (JSON.parse(raw) as Row[]) : []
  } catch {
    return []
  }
}

const rows: Row[] = load()

function persist() {
  if (!persistent) return
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(rows))
  } catch {
    // Storage full or blocked: the demo still works for this tab.
  }
}

const strip = ({ history: _history, ...app }: Row): Application => app
const find = (id: number) => rows.find((r) => r.id === id) ?? notFound('Application')

function furthestStage(history: StatusChange[]): FunnelStage {
  let best = 0
  for (const { status } of history) {
    const index = FUNNEL_STAGES.indexOf(status as FunnelStage)
    if (index > best) best = index
  }
  return FUNNEL_STAGES[best]
}

function mondayOf(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return d
}

export const mockApplications = {
  list: () => rows.map(strip).sort((a, b) => b.updated_at.localeCompare(a.updated_at)),

  create(data: ApplicationCreate, offer: JobOfferListItem): Application {
    const now = new Date().toISOString()
    const status = data.status ?? 'applied'
    const applied = status === 'saved' ? null : (data.applied_at ?? now)
    const row: Row = {
      id: newId(),
      job_offer: offer,
      status,
      resume_id: data.resume_id ?? null,
      notes: data.notes ?? null,
      applied_at: applied,
      interview_at: null,
      created_at: now,
      updated_at: now,
      history: [{ status, changed_at: now }],
    }
    rows.push(row)
    persist()
    return strip(row)
  },

  update(id: number, data: ApplicationUpdate): Application {
    const row = find(id)
    const now = new Date().toISOString()
    if (data.status && data.status !== row.status)
      row.history.push({ status: data.status, changed_at: now })
    Object.assign(row, data, { updated_at: now })
    // Moving a saved offer on (e.g. to applied) is when the user applied.
    if (row.status !== 'saved' && !row.applied_at) row.applied_at = data.applied_at ?? now
    persist()
    return strip(row)
  },

  remove(id: number): void {
    rows.splice(rows.indexOf(find(id)), 1)
    persist()
  },

  history: (id: number): StatusChange[] => find(id).history,

  forOffer: (offerId: number) => rows.find((r) => r.job_offer.id === offerId),

  stale(): StaleStage[] {
    const now = Date.now()
    return STALE_RULES.map(([stage, afterDays]) => {
      const inStage = rows.filter((r) => r.status === stage)
      const items: StaleStage['items'] = []
      inStage.forEach((r) => {
        const last = [...r.history].reverse().find((h) => h.status === stage)
        let since = last?.changed_at ?? r.updated_at
        if (stage === 'interview' && r.interview_at) {
          if (new Date(r.interview_at).getTime() > now) return
          if (r.interview_at > since) since = r.interview_at
        }
        const days = Math.floor((now - new Date(since).getTime()) / DAY)
        if (days >= afterDays)
          items.push({
            application_id: r.id,
            job_offer_id: r.job_offer.id,
            title: r.job_offer.title,
            company_name: r.job_offer.company_name,
            since,
            days,
          })
      })
      items.sort((a, b) => b.days - a.days)
      return { stage, after_days: afterDays, total: inStage.length, items }
    })
  },

  stats(range: StatsRange): ApplicationStats {
    const since = range === 'all' ? 0 : Date.now() - (range === '30d' ? 30 : 90) * DAY
    // Saved-only rows never entered the funnel.
    const inRange = rows.filter((r) => r.applied_at && new Date(r.applied_at).getTime() >= since)

    const reachedIndex = inRange.map((r) => FUNNEL_STAGES.indexOf(furthestStage(r.history)))
    const funnel = FUNNEL_STAGES.map((stage, i) => ({
      stage,
      reached: reachedIndex.filter((r) => r >= i).length,
    }))

    const outcomeMap = new Map<string, number>()
    inRange.forEach((r) => {
      const stage = furthestStage(r.history)
      if (stage === 'accepted') return
      const key = `${stage}|${r.status}`
      outcomeMap.set(key, (outcomeMap.get(key) ?? 0) + 1)
    })
    const outcomes = [...outcomeMap].map(([key, count]) => {
      const [stage, status] = key.split('|') as [FunnelStage, ApplicationStatus]
      return { stage, status, count }
    })

    const firstDate =
      range === 'all' ? Math.min(...rows.map((r) => new Date(r.created_at).getTime())) : since
    const weekly: ApplicationStats['weekly'] = []
    for (
      let w = mondayOf(new Date(firstDate));
      w.getTime() <= Date.now();
      w = new Date(w.getTime() + 7 * DAY)
    ) {
      const start = w.getTime()
      const end = start + 7 * DAY
      const within = (iso: string | null) => {
        const t = iso ? new Date(iso).getTime() : NaN
        return t >= start && t < end
      }
      weekly.push({
        week_start: dayKey(w),
        saved: rows.filter((r) =>
          r.history.some((h) => h.status === 'saved' && within(h.changed_at)),
        ).length,
        applied: rows.filter((r) => within(r.applied_at)).length,
        replied: rows.filter((r) => within(firstReplyAt(r))).length,
      })
    }

    const replied = inRange.filter((r) => firstReplyAt(r) !== null).length
    return { range, funnel, outcomes, weekly, replied }
  },

  calendar(from: string, to: string): CalendarEvent[] {
    const events: CalendarEvent[] = []
    const inside = (iso: string | null) => {
      if (!iso) return false
      const key = dayKey(new Date(iso))
      return key >= from && key <= to
    }
    const base = (r: Row) => ({
      title: r.job_offer.title,
      company_name: r.job_offer.company_name,
      job_offer_id: r.job_offer.id,
      application_id: r.id,
    })

    for (const r of rows) {
      r.history.forEach((h) => {
        if (!inside(h.changed_at) || h.status === 'saved') return
        if (h.status === 'applied') {
          events.push({
            ...base(r),
            date: dayKey(new Date(h.changed_at)),
            kind: 'applied',
            status: 'applied',
            time: null,
          })
        } else if (h.status !== 'interview') {
          events.push({
            ...base(r),
            date: dayKey(new Date(h.changed_at)),
            kind: 'status_change',
            status: h.status,
            time: null,
          })
        }
      })
      if (inside(r.interview_at)) {
        const at = new Date(r.interview_at!)
        events.push({
          ...base(r),
          date: dayKey(at),
          kind: 'interview',
          status: 'interview',
          time: at.toTimeString().slice(0, 5),
        })
      }
    }

    for (const r of rows) {
      const offer = r.job_offer
      if (r.status === 'rejected' || r.status === 'declined' || !inside(offer.deadline)) continue
      events.push({
        date: dayKey(new Date(offer.deadline!)),
        kind: 'deadline',
        title: offer.title,
        company_name: offer.company_name,
        job_offer_id: offer.id,
        application_id: r.id,
        status: null,
        time: null,
      })
    }
    return events.sort((a, b) => a.date.localeCompare(b.date))
  },
}
