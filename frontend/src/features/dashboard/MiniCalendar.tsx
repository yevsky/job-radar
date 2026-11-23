import { useState } from 'react'
import { Link } from 'react-router-dom'

import { getCalendar, type CalendarEvent } from '@/api/applications'
import { Icon } from '@/components/Icon'
import { dayKey, relativeDays } from '@/lib/format'
import { statusColor } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

const monthFmt = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

function eventColor(e: CalendarEvent): string {
  if (e.kind === 'interview') return 'var(--st-interview)'
  if (e.kind === 'deadline') return 'var(--st-rejected)'
  if (e.kind === 'applied') return 'var(--st-applied)'
  return e.status ? statusColor(e.status) : 'var(--text-faint)'
}

/** Monday-first weeks covering the month of `month`. */
function monthGrid(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1, 12)
  const start = new Date(first)
  start.setDate(1 - ((first.getDay() + 6) % 7))
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0, 12)
  const days: Date[] = []
  for (const d = new Date(start); d <= last || days.length % 7 !== 0; d.setDate(d.getDate() + 1)) {
    days.push(new Date(d))
  }
  return days
}

function nextTwoWeeks(): [string, string] {
  const today = new Date()
  const later = new Date(today)
  later.setDate(today.getDate() + 14)
  return [dayKey(today), dayKey(later)]
}

/** A small month view with a dot per kind of event, then the next interviews and deadlines. */
export function MiniCalendar() {
  const [month, setMonth] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const days = monthGrid(month)
  const from = dayKey(days[0])
  const to = dayKey(days[days.length - 1])
  const events = useAsync(() => getCalendar(from, to), [from, to])
  const [[soonFrom, soonTo]] = useState(nextTwoWeeks)
  const soon = useAsync(() => getCalendar(soonFrom, soonTo), [soonFrom, soonTo])

  const byDay = new Map<string, string[]>()
  for (const e of events.data ?? []) {
    const colors = byDay.get(e.date) ?? []
    const color = eventColor(e)
    if (!colors.includes(color)) colors.push(color)
    byDay.set(e.date, colors)
  }
  const today = dayKey(new Date())
  const upcoming = (soon.data ?? [])
    .filter((e) => e.kind === 'interview' || e.kind === 'deadline')
    .slice(0, 3)

  const shift = (by: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + by, 1))

  return (
    <section className="card">
      <div className="card-head" style={{ marginBottom: 12, alignItems: 'center' }}>
        <h2>{monthFmt.format(month)}</h2>
        <div className="row" style={{ gap: 2 }}>
          <button
            className="btn btn-ghost btn-icon"
            onClick={() => shift(-1)}
            aria-label="Previous month"
          >
            <Icon name="left" size={18} />
          </button>
          <button
            className="btn btn-ghost btn-icon"
            onClick={() => shift(1)}
            aria-label="Next month"
          >
            <Icon name="right" size={18} />
          </button>
        </div>
      </div>
      <div className="mini-cal" style={{ opacity: events.loading ? 0.6 : 1 }}>
        {WEEKDAYS.map((d) => (
          <div key={d} className="mini-cal-wd">
            {d}
          </div>
        ))}
        {days.map((d) => {
          const key = dayKey(d)
          const out = d.getMonth() !== month.getMonth()
          const dots = byDay.get(key) ?? []
          return (
            <div
              key={key}
              className="mini-cal-day"
              data-out={out || undefined}
              data-today={key === today || undefined}
            >
              {d.getDate()}
              <span className="mini-cal-dots">
                {dots.slice(0, 3).map((c) => (
                  <i key={c} style={{ background: key === today ? 'currentColor' : c }} />
                ))}
              </span>
            </div>
          )
        })}
      </div>
      <div className="mini-cal-next">
        {upcoming.length === 0 && !soon.loading && (
          <p className="small muted">No interviews or deadlines in the next 14 days.</p>
        )}
        {upcoming.map((e, i) => (
          <div key={i} className="small">
            <span style={{ color: eventColor(e), fontWeight: 600 }}>
              {e.kind === 'interview' ? 'Interview' : 'Deadline'}{' '}
              {relativeDays(`${e.date}T12:00:00`)}
              {e.time && ` · ${e.time}`}
            </span>{' '}
            <Link
              to={
                e.application_id
                  ? `/applications?open=${e.application_id}`
                  : `/offers/${e.job_offer_id}`
              }
            >
              {e.company_name}
            </Link>
          </div>
        ))}
        <Link to="/calendar" className="small">
          Open calendar
        </Link>
      </div>
    </section>
  )
}
