import { Link } from 'react-router-dom'

import { getStale, type StaleStage } from '@/api/applications'
import { ErrorBox, Loading } from '@/components/ui'
import { statusColor, statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

/** The rule behind each row, in words. */
const RULE: Record<StaleStage['stage'], (days: number) => string> = {
  saved: (d) => `Saved ${d}+ days ago and not sent`,
  applied: (d) => `No reply for ${d}+ days`,
  screening: (d) => `No next step for ${d}+ days`,
  interview: (d) => `No feedback ${d}+ days after the interview`,
  offer: (d) => `Waiting on your answer for ${d}+ days`,
}

/** How many squares the meter draws at most; bigger stages show a number instead. */
const METER_MAX = 8

const daysLabel = (days: number) => (days === 1 ? '1 day' : `${days} days`)

/** Per status: which applications haven't moved for longer than that status allows. */
export function StaleCard() {
  const stale = useAsync(() => getStale(), [])
  const rows = stale.data ?? []
  const stuck = rows.reduce((n, r) => n + r.items.length, 0)
  const open = rows.reduce((n, r) => n + r.total, 0)

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Stale by stage</h2>
          <p>
            {stale.data
              ? stuck
                ? `${stuck} of ${open} open ${open === 1 ? 'item has' : 'items have'} not moved for a while.`
                : 'Everything is moving.'
              : ' '}
          </p>
        </div>
      </div>
      {stale.error && <ErrorBox error={stale.error} onRetry={stale.reload} />}
      {stale.loading && !stale.data && <Loading />}
      <div className="stale-rows">
        {rows.map((row) => (
          <div className="stale-row" key={row.stage}>
            <div className="stale-name">
              <span className="dot" style={{ background: statusColor(row.stage) }} />
              {statusLabel[row.stage]}
            </div>
            <div
              className="stale-meter"
              role="img"
              aria-label={`${row.items.length} of ${row.total} stale`}
            >
              {row.total > METER_MAX ? (
                <span className="small muted">
                  {row.items.length}/{row.total}
                </span>
              ) : (
                Array.from({ length: row.total }, (_, i) => (
                  <i
                    key={i}
                    style={{
                      background:
                        i < row.items.length ? statusColor(row.stage) : 'var(--surface-2)',
                    }}
                  />
                ))
              )}
            </div>
            <div className="stale-body">
              <div className="small muted">
                {row.items.length > 0 && (
                  <b className="stale-count">
                    {row.items.length} of {row.total}
                  </b>
                )}
                {row.items.length > 0 && ' · '}
                {RULE[row.stage](row.after_days)}
              </div>
              <div className="stale-items">
                {row.items.length === 0 ? (
                  <span className="small stale-ok">
                    {row.total ? 'All moving' : 'Nothing here'}
                  </span>
                ) : (
                  row.items.map((item) => (
                    <Link
                      key={item.application_id}
                      to={`/applications?open=${item.application_id}`}
                      className="stale-item"
                      title={item.title}
                    >
                      {item.company_name}
                      <span className="faint">{daysLabel(item.days)}</span>
                    </Link>
                  ))
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
