import { useState } from 'react'

import { getAnalysis, runAnalysis, type AiAnalysis } from '@/api/analysis'
import { listResumes } from '@/api/resumes'
import { Icon } from '@/components/Icon'
import { DemoBadge, ErrorBox, Loading } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { useAsync } from '@/lib/useAsync'

import { ScoreRing } from './ScoreRing'
import { scoreBand } from './scoreBand'

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
      {a && <AnalysisResult a={a} />}
    </section>
  )
}

function AnalysisResult({ a }: { a: AiAnalysis }) {
  const band = scoreBand(a.score)
  return (
    <div className="stack" style={{ gap: 22 }}>
      <div className="row" style={{ gap: 24, flexWrap: 'nowrap', alignItems: 'center' }}>
        <ScoreRing score={a.score} />
        <div>
          <div style={{ color: band.color, fontWeight: 600 }}>{band.label}</div>
          {a.summary && <p style={{ marginTop: 4 }}>{a.summary}</p>}
        </div>
      </div>

      <div className="grid-2">
        <div>
          <h3 style={{ marginBottom: 8 }}>Why</h3>
          <ul className="bullets">
            {a.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 style={{ marginBottom: 8 }}>Red flags</h3>
          {a.red_flags.length ? (
            <ul className="bullets bullets-plain">
              {a.red_flags.map((f) => (
                <li
                  key={f}
                  className="row"
                  style={{ flexWrap: 'nowrap', alignItems: 'flex-start', color: 'var(--danger)' }}
                >
                  <Icon name="alert" size={16} />
                  <span style={{ color: 'var(--text)' }}>{f}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">None found.</p>
          )}
        </div>
      </div>

      <div className="grid-2">
        <SkillList
          title="Skills you have"
          skills={a.matched_skills}
          className="chip-match"
          empty="None of the listed skills."
        />
        <SkillList
          title="Skills to learn"
          skills={a.missing_skills}
          className="chip-miss"
          empty="Nothing missing."
        />
      </div>

      <p className="small faint">
        {a.provider}/{a.model} · prompt {a.prompt_version} · {formatDate(a.created_at)}
      </p>
    </div>
  )
}

function SkillList({
  title,
  skills,
  className,
  empty,
}: {
  title: string
  skills: string[]
  className: string
  empty: string
}) {
  return (
    <div>
      <h3 style={{ marginBottom: 8 }}>
        {title} <span className="muted small">({skills.length})</span>
      </h3>
      {skills.length ? (
        <div className="row" style={{ gap: 6 }}>
          {skills.map((s) => (
            <span key={s} className={`chip ${className}`}>
              {s}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted small">{empty}</p>
      )}
    </div>
  )
}
