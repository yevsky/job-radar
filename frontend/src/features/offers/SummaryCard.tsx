import { useState } from 'react'

import {
  getOfferSummary,
  MIN_SUMMARY_DESCRIPTION,
  runOfferSummary,
  type OfferSummary,
} from '@/api/jobOffers'
import { Icon } from '@/components/Icon'
import { ErrorBox, Loading } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { workModeLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

/**
 * "Summary": the AI's short version of the posting. One per offer, the same for everyone,
 * so it is made once and then read; "Summarise again" replaces it.
 */
export function SummaryCard({
  offerId,
  description,
}: {
  offerId: number
  description: string | null
}) {
  const summary = useAsync(() => getOfferSummary(offerId), [offerId])
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<Error>()
  const canSummarise = (description ?? '').trim().length >= MIN_SUMMARY_DESCRIPTION

  async function run() {
    setRunning(true)
    setRunError(undefined)
    try {
      summary.setData(await runOfferSummary(offerId))
    } catch (err) {
      setRunError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setRunning(false)
    }
  }

  const s = summary.data
  return (
    <section className="card" aria-busy={running}>
      <div className="card-head">
        <div>
          <h2>Summary</h2>
          <p>The posting in 30 seconds, read by the AI. The offer text is untrusted data.</p>
        </div>
        <button
          className="btn"
          onClick={run}
          disabled={running || !canSummarise}
          title={canSummarise ? undefined : 'This offer has no description to summarise.'}
        >
          <Icon name="sparkle" size={16} />
          {running ? 'Summarising…' : s ? 'Summarise again' : 'Summarise'}
        </button>
      </div>

      {summary.loading && !s && <Loading />}
      {summary.error && <ErrorBox error={summary.error} onRetry={summary.reload} />}
      {runError && <ErrorBox error={runError} />}
      {!summary.loading && !s && !running && (
        <p className="muted">
          {canSummarise
            ? 'Not summarised yet. It takes a few seconds, and everyone who sees this offer gets the same summary.'
            : 'No description was saved, so there is nothing to summarise. Open the original posting.'}
        </p>
      )}
      {s && <SummaryDetails s={s} />}
    </section>
  )
}

export function SummaryDetails({ s }: { s: OfferSummary }) {
  const lists: [string, string[]][] = [
    ["What you'll do", s.responsibilities],
    ['Must have', s.must_have],
    ['Nice to have', s.nice_to_have],
    ['They offer', s.benefits],
  ]
  return (
    <div className="stack" style={{ gap: 16 }}>
      <p style={{ fontSize: '1.05rem', maxWidth: '70ch' }}>{s.overview}</p>
      {(s.salary || s.work_mode) && (
        <div className="row" style={{ gap: 8 }}>
          {s.salary && <span className="tag tag-new">{s.salary}</span>}
          {s.work_mode && <span className="tag tag-info">{workModeLabel[s.work_mode]}</span>}
        </div>
      )}
      <div className="summary-grid">
        {lists
          .filter(([, items]) => items.length > 0)
          .map(([title, items]) => (
            <div key={title}>
              <h3 className="small muted" style={{ marginBottom: 6 }}>
                {title}
              </h3>
              <ul className="summary-list">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
      </div>
      {s.missing_info.length > 0 && (
        <p className="notice">
          <Icon name="alert" size={14} /> Not in the posting: {s.missing_info.join(', ')}.
        </p>
      )}
      <p className="hint">
        By {s.summary_with} · {s.prompt_version} · {formatDate(s.created_at)}
      </p>
    </div>
  )
}
