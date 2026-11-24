import { useState, type ReactNode } from 'react'

import { makeInsights, type Resume } from '@/api/resumes'
import { Icon } from '@/components/Icon'
import { experienceLabel } from '@/lib/labels'

/**
 * The career snapshot of one CV: a first-person summary, the level code counted, the fields
 * and areas of expertise, job titles to search for, what to learn next and advice.
 *
 * On the profile page a role can become the desired position (onUseRole fills the form; the
 * user still saves) and `picker` chooses the CV. onRegenerated shows a button that asks the
 * AI to write the snapshot again.
 */
export function CareerSnapshot({
  resume,
  onUseRole,
  onRegenerated,
  picker,
}: {
  resume: Resume
  onUseRole?: (role: string) => void
  onRegenerated?: (resume: Resume) => void
  picker?: ReactNode
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const insights = resume.insights
  const x = resume.extracted

  async function regenerate() {
    if (!onRegenerated) return
    setBusy(true)
    setError(undefined)
    try {
      onRegenerated(await makeInsights(resume.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not write the snapshot')
    } finally {
      setBusy(false)
    }
  }

  const regenerateButton = onRegenerated && (
    <button type="button" className="btn btn-sm" onClick={regenerate} disabled={busy}>
      <Icon name="sparkle" size={14} />
      {busy ? 'Writing…' : insights ? 'Write again' : 'Write snapshot'}
    </button>
  )

  return (
    <section className="card" aria-busy={busy}>
      <div className="card-head">
        <div>
          <h2>Career snapshot</h2>
          <p>
            From &ldquo;{resume.label}&rdquo;
            {resume.insights_with && ` · written by ${resume.insights_with}`}
          </p>
        </div>
        <div className="row">
          {picker}
          {regenerateButton}
        </div>
      </div>
      {error && (
        <p className="error-text" style={{ marginBottom: 12 }}>
          {error}
        </p>
      )}
      {!insights ? (
        <p className="muted">
          No snapshot yet. The AI didn&apos;t answer when the CV was uploaded
          {onRegenerated ? ': try again.' : '. Write it again on the My CVs page.'}
        </p>
      ) : (
        <div className="stack" style={{ gap: 20 }}>
          <Part title="Experience summary">
            <p style={{ maxWidth: '75ch' }}>{insights.summary}</p>
          </Part>

          <div className="snapshot-grid">
            {x?.experience_level && (
              <Part title="Current level">
                <div className="snapshot-level">
                  {experienceLabel[x.experience_level]}
                  {yearsText(x.experience_years)}
                </div>
              </Part>
            )}
            {insights.industries.length > 0 && (
              <Part title="Industry focus">
                <Chips items={insights.industries} className="tag tag-new" />
              </Part>
            )}
          </div>

          {insights.expertise.length > 0 && (
            <Part title="Technical areas & expertise">
              <Chips items={insights.expertise} className="chip" />
            </Part>
          )}

          {x && x.locations.length > 0 && (
            <Part title="Location preferences">
              <Chips items={x.locations} className="tag tag-info" icon="location" />
            </Part>
          )}

          <div className="snapshot-grid">
            {insights.roles.length > 0 && (
              <Part title="Recommended role titles">
                <ul className="snapshot-roles">
                  {insights.roles.map((role) => (
                    <li key={role}>
                      <Icon name="check" size={14} />
                      <span className="grow">{role}</span>
                      {onUseRole && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => onUseRole(role)}
                          title="Use as your desired position"
                          aria-label={`Use ${role} as desired position`}
                        >
                          Use
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </Part>
            )}
            {insights.growth.length > 0 && (
              <Part title="Worth learning next">
                <Chips items={insights.growth} className="chip" />
              </Part>
            )}
          </div>

          {insights.advice && (
            <Part title="Career search guidance">
              <p className="snapshot-advice">{insights.advice}</p>
            </Part>
          )}
        </div>
      )}
    </section>
  )
}

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="small muted" style={{ marginBottom: 8 }}>
        {title}
      </h3>
      {children}
    </div>
  )
}

function Chips({
  items,
  className,
  icon,
}: {
  items: string[]
  className: string
  icon?: 'location'
}) {
  return (
    <div className="snapshot-chips">
      {items.map((item) => (
        <span key={item} className={className}>
          {icon && <Icon name={icon} size={12} />} {item}
        </span>
      ))}
    </div>
  )
}

/** ' · 8 months of work' / ' · 2.5 years of work', when the backend counted the years. */
function yearsText(years: number | null | undefined): string {
  if (years === null || years === undefined) return ''
  const shown = years < 1 ? `${Math.round(years * 12)} months` : `${+years.toFixed(1)} years`
  return ` · ${shown} of work`
}
