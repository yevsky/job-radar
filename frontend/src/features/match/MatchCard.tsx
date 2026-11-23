import { useState } from 'react'

import { getAnalysis, runAnalysis } from '@/api/analysis'
import { listResumes } from '@/api/resumes'
import { Icon } from '@/components/Icon'
import { DemoBadge, ErrorBox, Loading } from '@/components/ui'
import { useAsync } from '@/lib/useAsync'

import { MatchDetails } from './MatchDetails'

/** "How you match": AI score, reasons, red flags and matched/missing skills for one offer. */
export function MatchCard({ offerId }: { offerId: number }) {
  const analysis = useAsync(() => getAnalysis(offerId), [offerId])
  const resumes = useAsync(() => listResumes(), [])
  const [resumeId, setResumeId] = useState<number | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<Error>()

  async function run() {
    setRunning(true)
    setRunError(undefined)
    try {
      analysis.setData(await runAnalysis(offerId, resumeId))
    } catch (err) {
      setRunError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setRunning(false)
    }
  }

  const a = analysis.data
  return (
    <section className="card" aria-busy={running}>
      <div className="card-head">
        <div>
          <div className="row">
            <h2>How you match</h2>
            <DemoBadge feature="analysis" />
          </div>
          <p>
            Scored against your profile{resumes.data?.length ? ' and the CV you pick' : ''}. The
            offer text is treated as untrusted data.
          </p>
        </div>
        <div className="row">
          {resumes.data && resumes.data.length > 0 && (
            <select
              className="select"
              style={{ width: 'auto' }}
              aria-label="CV to compare"
              value={resumeId ?? ''}
              onChange={(e) => setResumeId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Profile only</option>
              {resumes.data.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          )}
          <button className="btn btn-primary" onClick={run} disabled={running}>
            <Icon name="sparkle" size={16} />
            {running ? 'Analysing…' : a ? 'Run again' : 'Analyse'}
          </button>
        </div>
      </div>

      {analysis.loading && !a && <Loading />}
      {analysis.error && <ErrorBox error={analysis.error} onRetry={analysis.reload} />}
      {runError && <ErrorBox error={runError} />}
      {!analysis.loading && !a && !running && (
        <p className="muted">
          Not analysed yet. Analysing takes a few seconds and uses your daily AI quota.
        </p>
      )}
      {a && <MatchDetails a={a} />}
    </section>
  )
}
