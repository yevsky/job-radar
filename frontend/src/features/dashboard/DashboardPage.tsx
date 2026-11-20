import { useState } from 'react'
import { Link } from 'react-router-dom'

import { getCalendar, getStats, type ApplicationStats, type StatsRange } from '@/api/applications'
import { getProfile } from '@/api/profile'
import { DemoBadge, ErrorBox, Loading, PageHeader, Segmented } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthContext'
import { dayKey, formatShort, greeting, pct, relativeDays } from '@/lib/format'
import { statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

import { FunnelChart } from './FunnelChart'
import { WeeklyChart, WeeklyLegend } from './WeeklyChart'

const RANGES: { value: StatsRange; label: string }[] = [
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: 'all', label: 'All time' },
]

function reached(stats: ApplicationStats, stage: string) {
  return stats.funnel.find((f) => f.stage === stage)?.reached ?? 0
}

function summary(stats: ApplicationStats): string {
  const sent = reached(stats, 'applied')
  const heard = reached(stats, 'screening')
  if (!sent) return 'Nothing sent in this period yet. Save a few offers and send the best one.'
  const rate = pct(heard, sent)
  const tone =
    rate >= 50
      ? "That's a solid run."
      : rate >= 20
        ? 'Keep going.'
        : 'Replies take time; the match card can help pick stronger offers.'
  return `You've sent ${sent} ${sent === 1 ? 'application' : 'applications'} and heard back from ${heard}. ${tone}`
}

export function DashboardPage() {
  const { user } = useAuth()
  const [range, setRange] = useState<StatsRange>('all')
  const stats = useAsync(() => getStats(range), [range])
  const profile = useAsync(() => getProfile(), [])
  const name = profile.data?.first_name || user?.email.split('@')[0]

  const s = stats.data
  const sent = s ? reached(s, 'applied') : 0
  const weeklyTotals = s?.weekly.reduce(
    (acc, w) => ({ saved: acc.saved + w.saved, applied: acc.applied + w.applied }),
    { saved: 0, applied: 0 },
  )

  return (
    <>
      <PageHeader
        icon="home"
        title={`${greeting()}, ${name}`}
        lead={s ? summary(s) : ' '}
        actions={
          <Link to="/search" className="btn btn-primary">
            Find jobs
          </Link>
        }
      />
      <div className="row" style={{ marginBottom: 24 }}>
        <span className="muted">Showing</span>
        <Segmented label="Time range" options={RANGES} value={range} onChange={setRange} />
        <DemoBadge feature="stats" />
      </div>

      {stats.error && <ErrorBox error={stats.error} onRetry={stats.reload} />}
      {stats.loading && !s && <Loading />}
      {s && (
        <div className="stack" style={{ gap: 24, opacity: stats.loading ? 0.6 : 1 }}>
          <section className="card">
            <div className="card-head">
              <div>
                <h2>Your funnel</h2>
                <p>How far each application got, and where the ones that stopped are now.</p>
              </div>
              <div className="stats">
                <Stat value={String(sent)} label="sent" />
                <Stat value={`${pct(reached(s, 'screening'), sent)}%`} label="heard back" />
                <Stat value={String(reached(s, 'interview'))} label="reached interview" />
              </div>
            </div>
            <FunnelChart stats={s} />
            <details style={{ marginTop: 20 }}>
              <summary>Show the numbers</summary>
              <table className="data">
                <thead>
                  <tr>
                    <th>Stage</th>
                    <th>Reached</th>
                    <th>Of previous</th>
                    <th>Stopped here</th>
                  </tr>
                </thead>
                <tbody>
                  {s.funnel.map((f, i) => (
                    <tr key={f.stage}>
                      <td>{statusLabel[f.stage]}</td>
                      <td>{f.reached}</td>
                      <td>{i === 0 ? '' : `${pct(f.reached, s.funnel[i - 1].reached)}%`}</td>
                      <td>
                        {s.outcomes
                          .filter((o) => o.stage === f.stage)
                          .map((o) => `${o.count} ${statusLabel[o.status].toLowerCase()}`)
                          .join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </section>

          <div className="split" style={{ gridTemplateColumns: 'minmax(0, 1fr) 320px' }}>
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Week by week</h2>
                  {weeklyTotals && (
                    <p>
                      You saved {weeklyTotals.saved} offers and sent {weeklyTotals.applied}{' '}
                      applications in this period.
                    </p>
                  )}
                </div>
                <WeeklyLegend />
              </div>
              <WeeklyChart weekly={s.weekly} />
              <details style={{ marginTop: 16 }}>
                <summary>Show the numbers</summary>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Week of</th>
                      <th>Saved</th>
                      <th>Applied</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.weekly.map((w) => (
                      <tr key={w.week_start}>
                        <td>{formatShort(`${w.week_start}T12:00:00`)}</td>
                        <td>{w.saved}</td>
                        <td>{w.applied}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </section>
            <ComingUp />
          </div>
        </div>
      )}
    </>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="stat-num">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function nextTwoWeeks(): [string, string] {
  const today = new Date()
  const later = new Date(today)
  later.setDate(today.getDate() + 14)
  return [dayKey(today), dayKey(later)]
}

/** Next two weeks: interviews and deadlines, from the calendar endpoint. */
function ComingUp() {
  const [[from, to]] = useState(nextTwoWeeks)
  const events = useAsync(() => getCalendar(from, to), [from, to])
  const upcoming = (events.data ?? []).filter(
    (e) => e.kind === 'interview' || e.kind === 'deadline',
  )
  return (
    <section className="card">
      <h2 style={{ marginBottom: 6 }}>Coming up</h2>
      <p className="muted small" style={{ marginBottom: 16 }}>
        Interviews and deadlines in the next 14 days.
      </p>
      {events.loading && <Loading />}
      {!events.loading && upcoming.length === 0 && <p className="muted">Nothing scheduled.</p>}
      <ul className="bullets bullets-plain" style={{ gap: 14 }}>
        {upcoming.map((e, i) => (
          <li key={i}>
            <div
              className="small"
              style={{
                color: e.kind === 'interview' ? 'var(--st-interview)' : 'var(--st-rejected)',
                fontWeight: 500,
              }}
            >
              {e.kind === 'interview' ? 'Interview' : 'Deadline'}{' '}
              {relativeDays(`${e.date}T12:00:00`)}
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
          </li>
        ))}
      </ul>
      <Link to="/calendar" className="small" style={{ display: 'inline-block', marginTop: 16 }}>
        Open calendar
      </Link>
    </section>
  )
}
