import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type { SearchResult } from '@/api/search'
import { Icon, type IconName } from '@/components/Icon'
import { formatDate } from '@/lib/format'
import { employmentLabel, experienceLabel } from '@/lib/labels'

import { CompanyTile } from './ResultCard'
import { formatSalary, isNew, isRemote, similarTo } from './searchUtils'

type Tab = 'offer' | 'similar'

/** Right-hand panel: everything we know about one result, before anything is saved. */
export function ResultDetail({
  result,
  all,
  savedId,
  saving,
  saveError,
  now,
  onSave,
  onSelect,
  onClose,
}: {
  result: SearchResult
  all: SearchResult[]
  savedId: number | undefined
  saving: boolean
  saveError: string | undefined
  now: number
  onSave: () => void
  onSelect: (url: string) => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<Tab>('offer')
  const similar = similarTo(result, all)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <aside className="detail" aria-label={result.title}>
      <div className="detail-tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'offer'} onClick={() => setTab('offer')}>
          Offer
        </button>
        <button role="tab" aria-selected={tab === 'similar'} onClick={() => setTab('similar')}>
          Similar ({similar.length})
        </button>
      </div>

      {tab === 'similar' ? (
        <div className="detail-body">
          {similar.length === 0 && (
            <p className="muted">No other result shares its technologies.</p>
          )}
          <div className="stack" style={{ gap: 10 }}>
            {similar.map((r) => (
              <button
                key={r.url}
                className="similar-item"
                onClick={() => {
                  onSelect(r.url)
                  setTab('offer')
                }}
              >
                <CompanyTile company={r.company_name} size={40} />
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span className="item-title">{r.title}</span>
                  <span className="small muted" style={{ display: 'block' }}>
                    {r.company_name} · {r.location}
                  </span>
                </span>
                {formatSalary(r) && <span className="salary small">{formatSalary(r)}</span>}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          <header className="detail-head">
            <CompanyTile company={result.company_name} size={72} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row" style={{ gap: 6 }}>
                {isNew(result, now) && <span className="tag tag-info">new</span>}
                <span className="tag tag-new">via {result.found_via}</span>
              </div>
              <h2 style={{ margin: '6px 0 4px' }}>{result.title}</h2>
              <p className="small muted">
                Company: <strong style={{ color: 'var(--text)' }}>{result.company_name}</strong>
              </p>
            </div>
            <div className="detail-actions">
              <div className="row" style={{ gap: 2, justifyContent: 'flex-end' }}>
                <a
                  className="btn btn-ghost btn-icon"
                  href={result.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  aria-label="Open the original posting"
                  title="Open the original posting"
                >
                  <Icon name="external" size={19} />
                </a>
                <button
                  className="btn btn-ghost btn-icon"
                  onClick={onClose}
                  aria-label="Close"
                  title="Close"
                >
                  <Icon name="x" size={19} />
                </button>
              </div>
              {savedId ? (
                <Link to={`/offers/${savedId}`} className="btn btn-primary">
                  <Icon name="check" size={16} /> Saved, open
                </Link>
              ) : (
                <button className="btn btn-primary" onClick={onSave} disabled={saving}>
                  <Icon name="bookmark" size={16} /> {saving ? 'Saving…' : 'Save to my offers'}
                </button>
              )}
            </div>
          </header>
          {saveError && (
            <p className="error-text" style={{ padding: '0 24px' }}>
              {saveError}
            </p>
          )}

          <DateBar
            postedAt={result.posted_at ?? null}
            deadline={result.deadline ?? null}
            now={now}
          />

          <section className="detail-block">
            {formatSalary(result) ? (
              <div className="salary" style={{ fontSize: '1.35rem' }}>
                {formatSalary(result)}{' '}
                <span className="muted small" style={{ fontWeight: 400 }}>
                  {result.salary_period === 'hour' ? 'net (B2B)' : 'gross'}
                </span>
              </div>
            ) : (
              <div className="muted">Salary not stated</div>
            )}
            <p className="small muted" style={{ marginTop: 4 }}>
              {result.employment_type
                ? employmentLabel[result.employment_type]
                : 'Contract type not stated'}
            </p>
          </section>

          <div className="fact-tiles">
            <FactTile
              icon="layers"
              label="level"
              value={
                result.experience_level ? experienceLabel[result.experience_level] : 'not stated'
              }
            />
            <FactTile
              icon="laptop"
              label="work mode"
              value={
                isRemote(result) ? 'remote' : result.location ? 'on-site / hybrid' : 'not stated'
              }
            />
            <FactTile icon="location" label="location" value={result.location ?? 'not stated'} />
          </div>

          <Collapsible title="About the offer">
            {result.description ? (
              <div style={{ whiteSpace: 'pre-wrap' }}>{result.description}</div>
            ) : (
              <p className="muted">
                The source gave no description. Open the original posting to read it.
              </p>
            )}
            <p className="hint" style={{ marginTop: 12 }}>
              Save it to get the AI match: score, reasons, red flags and missing skills.
            </p>
          </Collapsible>

          {result.technologies && result.technologies.length > 0 && (
            <Collapsible title="Tech stack">
              <div className="result-techs" style={{ marginTop: 0 }}>
                {result.technologies.map((t) => (
                  <span key={t} className="tech">
                    {t}
                  </span>
                ))}
              </div>
            </Collapsible>
          )}
        </>
      )}
    </aside>
  )
}

function FactTile({ icon, label, value }: { icon: IconName; label: string; value: string }) {
  return (
    <div className="fact-tile">
      <span className="fact-icon">
        <Icon name={icon} size={20} />
      </span>
      <span className="small muted">{label}:</span>
      <strong>{value}</strong>
    </div>
  )
}

function Collapsible({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <section className="detail-block">
      <button
        className="filter-head"
        style={{ padding: 0 }}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <h2 style={{ fontSize: '1.2rem' }}>{title}</h2>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} size={18} />
      </button>
      {open && <div style={{ marginTop: 12 }}>{children}</div>}
    </section>
  )
}

/** "posted … — deadline …" with how much of that window has passed. */
function DateBar({
  postedAt,
  deadline,
  now,
}: {
  postedAt: string | null
  deadline: string | null
  now: number
}) {
  if (!postedAt && !deadline) return null
  let pct = 0
  if (postedAt && deadline) {
    const start = new Date(postedAt).getTime()
    const end = new Date(deadline).getTime()
    pct = Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100))
  }
  return (
    <div className="date-bar">
      {postedAt && deadline && (
        <div className="date-track">
          <span style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="row small muted" style={{ justifyContent: 'space-between' }}>
        <span>{postedAt ? `posted ${formatDate(postedAt)}` : ''}</span>
        <span>{deadline ? `apply by ${formatDate(deadline)}` : 'no deadline'}</span>
      </div>
    </div>
  )
}
