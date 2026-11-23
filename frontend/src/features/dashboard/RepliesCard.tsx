import type { ApplicationStats } from '@/api/applications'
import type { ApplicationStatus } from '@/api/enums'
import { pct } from '@/lib/format'
import { statusColor } from '@/lib/labels'

interface Row {
  status: ApplicationStatus
  label: string
  count: number
  note?: string
}

/**
 * Every outcome as a share of all applications sent, so 1 offer from 100 applications is 1%.
 * The positive rows count every application that got at least that far.
 */
export function RepliesCard({ stats }: { stats: ApplicationStats }) {
  const sent = stats.funnel[0]?.reached ?? 0
  const reached = (stage: string) => stats.funnel.find((f) => f.stage === stage)?.reached ?? 0
  const now = (status: ApplicationStatus) =>
    stats.outcomes.filter((o) => o.status === status).reduce((n, o) => n + o.count, 0)

  const positive = reached('screening')
  const negative = Math.max(0, stats.replied - positive)
  const silent = Math.max(0, sent - stats.replied)
  const waiting = stats.outcomes
    .filter((o) => o.stage === 'applied' && o.status === 'applied')
    .reduce((n, o) => n + o.count, 0)

  const groups: { title: string; rows: Row[] }[] = [
    {
      title: 'Positive',
      rows: [
        { status: 'screening', label: 'Screening call', count: positive },
        { status: 'interview', label: 'Interview', count: reached('interview') },
        { status: 'offer', label: 'Offer', count: reached('offer') },
        { status: 'accepted', label: 'Accepted', count: reached('accepted') },
      ],
    },
    {
      title: 'Negative',
      rows: [
        { status: 'rejected', label: 'Rejected', count: now('rejected'), note: 'at any stage' },
        { status: 'saved', label: 'No reply yet', count: waiting },
      ],
    },
    {
      title: 'Your call',
      rows: [{ status: 'declined', label: 'You declined', count: now('declined') }],
    },
  ]

  return (
    <section className="card">
      <div className="card-head" style={{ marginBottom: 12 }}>
        <h2>Replies</h2>
        <span className="small muted">% of all {sent} sent</span>
      </div>
      {sent === 0 ? (
        <p className="muted">Nothing sent in this period yet.</p>
      ) : (
        <>
          <div className="reply-split" role="img" aria-label="First replies">
            {positive > 0 && <div style={{ flex: positive, background: 'var(--success)' }} />}
            {negative > 0 && <div style={{ flex: negative, background: 'var(--danger)' }} />}
            {silent > 0 && <div style={{ flex: silent, background: 'var(--surface-2)' }} />}
          </div>
          <p className="small muted" style={{ marginBottom: 6 }}>
            First reply: <b style={{ color: 'var(--success)' }}>{positive} positive</b>,{' '}
            <b style={{ color: 'var(--danger)' }}>{negative} negative</b>, {silent} none
          </p>
          {groups.map((g) => (
            <div key={g.title}>
              <div className="reply-group">{g.title}</div>
              {g.rows.map((r) => (
                <div className="reply-row" key={r.label}>
                  <span className="dot" style={{ background: statusColor(r.status) }} />
                  <span>
                    {r.label}
                    {r.note && <span className="small muted"> {r.note}</span>}
                  </span>
                  <b>{r.count}</b>
                  <span className="reply-pct">{pct(r.count, sent)}%</span>
                  <span className="reply-bar">
                    <i
                      style={{ width: `${pct(r.count, sent)}%`, background: statusColor(r.status) }}
                    />
                  </span>
                </div>
              ))}
            </div>
          ))}
        </>
      )}
    </section>
  )
}
