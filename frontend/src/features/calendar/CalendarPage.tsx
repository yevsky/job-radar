import { useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'

import { getCalendar, type CalendarEvent, type CalendarEventKind } from '@/api/applications'
import { Icon } from '@/components/Icon'
import { DemoBadge, ErrorBox, PageHeader } from '@/components/ui'
import { dayKey } from '@/lib/format'
import { statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

const KIND: Record<CalendarEventKind, { label: string; color: string }> = {
  applied: { label: 'Applied', color: 'var(--st-applied)' },
  status_change: { label: 'Status change', color: 'var(--st-screening)' },
  interview: { label: 'Interview', color: 'var(--st-interview)' },
  deadline: { label: 'Deadline', color: 'var(--st-rejected)' },
}

const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const monthFmt = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })
const dayFmt = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

/** 6 weeks starting on the Monday on/before the 1st, so every month has the same height. */
function monthGrid(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1)
  const start = new Date(first)
  start.setDate(first.getDate() - ((first.getDay() + 6) % 7))
  return Array.from(
    { length: 42 },
    (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
  )
}

function describe(e: CalendarEvent): string {
  if (e.kind === 'status_change' && e.status) return `${statusLabel[e.status]}: ${e.company_name}`
  if (e.kind === 'interview') return `${e.time ? `${e.time} ` : ''}Interview: ${e.company_name}`
  return `${KIND[e.kind].label}: ${e.company_name}`
}

export function CalendarPage() {
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  )
  const [selected, setSelected] = useState(() => dayKey(new Date()))
  const days = useMemo(() => monthGrid(month), [month])
  const from = dayKey(days[0])
  const to = dayKey(days[days.length - 1])
  const events = useAsync(() => getCalendar(from, to), [from, to])

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    for (const e of events.data ?? []) map.set(e.date, [...(map.get(e.date) ?? []), e])
    return map
  }, [events.data])

  const today = dayKey(new Date())
  const shift = (n: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + n, 1))
  const selectedEvents = byDay.get(selected) ?? []

  return (
    <>
      <PageHeader
        icon="calendar"
        title="Calendar"
        lead="Applications sent, status changes, interviews and deadlines of offers you track."
        actions={<DemoBadge feature="calendar" />}
      />
      {events.error && <ErrorBox error={events.error} onRetry={events.reload} />}
      <div className="split" style={{ gridTemplateColumns: 'minmax(0, 1fr) 300px' }}>
        <section>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
            <h2>{monthFmt.format(month)}</h2>
            <div className="row">
              <button
                className="btn btn-icon"
                onClick={() => shift(-1)}
                aria-label="Previous month"
              >
                <Icon name="left" />
              </button>
              <button
                className="btn btn-sm"
                onClick={() => {
                  setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
                  setSelected(today)
                }}
              >
                Today
              </button>
              <button className="btn btn-icon" onClick={() => shift(1)} aria-label="Next month">
                <Icon name="right" />
              </button>
            </div>
          </div>
          <div className="cal" style={{ opacity: events.loading ? 0.6 : 1 }}>
            {DOW.map((d) => (
              <div key={d} className="cal-dow">
                {d}
              </div>
            ))}
            {days.map((d) => {
              const key = dayKey(d)
              const list = byDay.get(key) ?? []
              return (
                <button
                  key={key}
                  className="cal-day"
                  data-outside={d.getMonth() !== month.getMonth()}
                  data-today={key === today}
                  aria-pressed={key === selected}
                  aria-label={`${dayFmt.format(d)}, ${list.length} events`}
                  onClick={() => setSelected(key)}
                >
                  <span className="cal-num">{d.getDate()}</span>
                  {list.slice(0, 3).map((e, i) => (
                    <span
                      key={i}
                      className="cal-event"
                      style={{ '--ev': KIND[e.kind].color } as CSSProperties}
                    >
                      {describe(e)}
                    </span>
                  ))}
                  {list.length > 3 && <span className="small faint">+{list.length - 3} more</span>}
                </button>
              )
            })}
          </div>
          <div className="row small muted" style={{ marginTop: 12, gap: 16 }}>
            {Object.values(KIND).map((k) => (
              <span key={k.label} className="row" style={{ gap: 6 }}>
                <span className="dot" style={{ background: k.color }} /> {k.label}
              </span>
            ))}
          </div>
        </section>

        <aside className="card" style={{ padding: 22 }}>
          <h3 style={{ marginBottom: 14 }}>{dayFmt.format(new Date(`${selected}T12:00:00`))}</h3>
          {selectedEvents.length === 0 ? (
            <p className="muted">Nothing on this day.</p>
          ) : (
            <ul className="bullets bullets-plain" style={{ gap: 14 }}>
              {selectedEvents.map((e, i) => (
                <li
                  key={i}
                  className="row"
                  style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}
                >
                  <span className="dot" style={{ background: KIND[e.kind].color, marginTop: 7 }} />
                  <div>
                    <div className="small muted">
                      {KIND[e.kind].label}
                      {e.kind === 'status_change' && e.status && ` → ${statusLabel[e.status]}`}
                      {e.time && ` · ${e.time}`}
                    </div>
                    <Link
                      to={
                        e.application_id
                          ? `/applications?open=${e.application_id}`
                          : `/offers/${e.job_offer_id}`
                      }
                    >
                      {e.title}
                    </Link>
                    <div className="small muted">{e.company_name}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </>
  )
}
