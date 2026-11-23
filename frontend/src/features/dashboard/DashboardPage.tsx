import { useState } from 'react'
import { Link } from 'react-router-dom'

import { getStats, type ApplicationStats, type StatsRange } from '@/api/applications'
import { DemoBadge, ErrorBox, Loading, PageHeader, Segmented } from '@/components/ui'
import { formatShort, pct } from '@/lib/format'
import { statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

import { FunnelChart } from './FunnelChart'
import { MiniCalendar } from './MiniCalendar'
import { RepliesCard } from './RepliesCard'
import { StaleCard } from './StaleCard'
import { WeeklyChart, WeeklyLegend } from './WeeklyChart'
import { applyStreak, padWeeks } from './weeks'

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
  if (!sent) return 'Nothing sent in this period yet. Save a few offers and send the best one.'
  return `You've sent ${sent} ${sent === 1 ? 'application' : 'applications'} and heard back from ${stats.replied}.`
}

export function DashboardPage() {
  const [range, setRange] = useState<StatsRange>('all')
  const stats = useAsync(() => getStats(range), [range])
  const s = stats.data
  const sent = s ? reached(s, 'applied') : 0

  return (
    <>
      <PageHeader
        icon="home"
        title="Your pipeline"
        lead={s ? summary(s) : ' '}
        actions={
          <>
            <Segmented label="Time range" options={RANGES} value={range} onChange={setRange} />
            <DemoBadge feature="stats" />
            <Link to="/search" className="btn btn-primary">
              Find jobs
            </Link>
          </>
        }
      />

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
                <Stat value={`${pct(s.replied, sent)}%`} label="heard back" />
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
                    <th>Of all sent</th>
                    <th>Stopped here</th>
                  </tr>
                </thead>
                <tbody>
                  {s.funnel.map((f, i) => (
                    <tr key={f.stage}>
                      <td>{statusLabel[f.stage]}</td>
                      <td>{f.reached}</td>
                      <td>{i === 0 ? '' : `${pct(f.reached, s.funnel[i - 1].reached)}%`}</td>
                      <td>{`${pct(f.reached, sent)}%`}</td>
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

          <div className="split dashboard-split">
            <div className="stack" style={{ gap: 24, minWidth: 0 }}>
              <WeekByWeek stats={s} range={range} />
              <StaleCard />
            </div>
            <div className="stack" style={{ gap: 24, minWidth: 0 }}>
              <MiniCalendar />
              <RepliesCard stats={s} />
            </div>
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

function WeekByWeek({ stats, range }: { stats: ApplicationStats; range: StatsRange }) {
  const weekly = padWeeks(stats.weekly, range)
  const real = stats.weekly
  const total = real.reduce((n, w) => n + w.applied, 0)
  const replies = real.reduce((n, w) => n + w.replied, 0)
  const thisWeek = real.at(-1)?.applied ?? 0
  const average = real.length ? total / real.length : 0
  const streak = applyStreak(real)

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Week by week</h2>
          <p>Offers saved, applications sent and replies that came in.</p>
        </div>
        <WeeklyLegend />
      </div>
      <div className="week-sum">
        <SumCell value={String(thisWeek)} label="sent this week" />
        <SumCell value={average.toFixed(1)} label="sent per week on average" />
        <SumCell
          value={String(replies)}
          label={replies === 1 ? 'reply in this period' : 'replies in this period'}
        />
        <SumCell
          value={`${streak} wk`}
          label={streak === 1 ? 'with an application' : 'in a row with an application'}
        />
      </div>
      <WeeklyChart weekly={weekly} />
      <details style={{ marginTop: 16 }}>
        <summary>Show the numbers</summary>
        <table className="data">
          <thead>
            <tr>
              <th>Week of</th>
              <th>Saved</th>
              <th>Applied</th>
              <th>Replies</th>
            </tr>
          </thead>
          <tbody>
            {real.map((w) => (
              <tr key={w.week_start}>
                <td>{formatShort(`${w.week_start}T12:00:00`)}</td>
                <td>{w.saved}</td>
                <td>{w.applied}</td>
                <td>{w.replied}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}

function SumCell({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="week-sum-num">{value}</div>
      <div className="small muted">{label}</div>
    </div>
  )
}
