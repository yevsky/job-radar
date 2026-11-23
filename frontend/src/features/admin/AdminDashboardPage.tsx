import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { getAdminStats, type AdminStats } from '@/api/admin'
import { APPLICATION_STATUSES } from '@/api/enums'
import { ErrorBox, Loading, PageHeader } from '@/components/ui'
import { statusColor, statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

import { BarChart } from './BarChart'

/** Admin: how the app is used, counted by GET /admin/stats. */
export function AdminDashboardPage() {
  const stats = useAsync(() => getAdminStats(), [])
  const s = stats.data
  return (
    <>
      <PageHeader
        icon="sliders"
        title="Admin dashboard"
        lead="How many people use JobRadar and what they do with it."
        actions={
          <button className="btn" onClick={stats.reload}>
            Refresh
          </button>
        }
      />
      {stats.loading && !s && <Loading />}
      {stats.error && <ErrorBox error={stats.error} onRetry={stats.reload} />}
      {s && <Dashboard s={s} />}
    </>
  )
}

function Dashboard({ s }: { s: AdminStats }) {
  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="grid-2">
        <Tile title="Users" to="/admin/users" link="Manage users">
          <Num value={s.users} label="accounts" />
          <Num value={s.admins} label="admins" />
          <Num value={s.new_users_last_7_days} label="new this week" />
        </Tile>
        <Tile title="Offers" to="/admin/offers" link="Imported offers">
          <Num value={s.public_offers} label="shown to everyone" />
          <Num value={s.hidden_offers} label="hidden" />
          <Num value={s.private_offers} label="private (saved by users)" />
        </Tile>
        <Tile title="Searches">
          <Num value={s.searches_today} label="today" />
          <Num value={s.searches_last_7_days} label="last 7 days" />
        </Tile>
        <Tile title="AI">
          <Num value={s.analyses} label="match analyses" />
          <Num value={s.conversations} label="assistant chats" />
        </Tile>
      </div>
      <div className="grid-2">
        <section className="card stack">
          <div className="card-head">
            <h2>Searches per day</h2>
            <p>The last 14 days</p>
          </div>
          <BarChart data={s.searches_by_day} label="Searches per day, last 14 days" />
        </section>
        <section className="card stack">
          <div className="card-head">
            <h2>New accounts per week</h2>
            <p>The last 8 weeks</p>
          </div>
          <BarChart data={s.signups_by_week} label="New accounts per week, last 8 weeks" />
        </section>
      </div>
      <section className="card stack">
        <div className="card-head">
          <h2>Applications by status</h2>
          <p>{s.applications} tracked by all users</p>
        </div>
        <StatusBars counts={s.applications_by_status} total={s.applications} />
      </section>
    </div>
  )
}

function Tile({
  title,
  to,
  link,
  children,
}: {
  title: string
  to?: string
  link?: string
  children: ReactNode
}) {
  return (
    <section className="card stack">
      <div className="card-head row" style={{ justifyContent: 'space-between' }}>
        <h2>{title}</h2>
        {to && (
          <Link className="small" to={to}>
            {link}
          </Link>
        )}
      </div>
      <div className="stats">{children}</div>
    </section>
  )
}

function Num({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="stat-num">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function StatusBars({
  counts,
  total,
}: {
  counts: AdminStats['applications_by_status']
  total: number
}) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      {APPLICATION_STATUSES.map((status) => {
        const n = counts[status] ?? 0
        const share = total ? (n / total) * 100 : 0
        return (
          <div key={status} className="row" style={{ gap: 12 }}>
            <span className="small" style={{ width: 90 }}>
              {statusLabel[status]}
            </span>
            <div style={{ flex: 1, background: 'var(--surface-2)', borderRadius: 4 }} aria-hidden>
              <div
                style={{
                  width: `${share}%`,
                  minWidth: n ? 4 : 0,
                  height: 10,
                  borderRadius: 4,
                  background: statusColor(status),
                }}
              />
            </div>
            <span className="small" style={{ width: 32, textAlign: 'right' }}>
              {n}
            </span>
          </div>
        )
      })}
    </div>
  )
}
