import type { AiAnalysis } from '@/api/analysis'
import { Icon } from '@/components/Icon'
import { formatDate } from '@/lib/format'

import { ScoreRing } from './ScoreRing'
import { scoreBand } from './scoreBand'

/** What the card needs: a stored analysis, or one the assistant made for a search result. */
export type MatchView = Pick<
  AiAnalysis,
  | 'score'
  | 'summary'
  | 'reasons'
  | 'red_flags'
  | 'matched_skills'
  | 'missing_skills'
  | 'provider'
  | 'model'
  | 'prompt_version'
> & { created_at?: string }

/** The body of the "How you match" card; also shown in the AI assistant chat. */
export function MatchDetails({ a }: { a: MatchView }) {
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
        {a.provider}/{a.model} · prompt {a.prompt_version}
        {a.created_at && ` · ${formatDate(a.created_at)}`}
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
