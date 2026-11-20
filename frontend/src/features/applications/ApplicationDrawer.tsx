import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'

import {
  deleteApplication,
  getApplicationHistory,
  updateApplication,
  type Application,
  type ApplicationUpdate,
} from '@/api/applications'
import { APPLICATION_STATUSES, type ApplicationStatus } from '@/api/enums'
import { listResumes } from '@/api/resumes'
import { Icon } from '@/components/Icon'
import { formatDate, formatTime } from '@/lib/format'
import { statusColor, statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

/** `<input type="datetime-local">` wants local "YYYY-MM-DDTHH:mm". */
function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function ApplicationDrawer({
  app,
  onClose,
  onChange,
  onDelete,
}: {
  app: Application
  onClose: () => void
  onChange: (a: Application) => void
  onDelete: () => void
}) {
  const history = useAsync(() => getApplicationHistory(app.id), [app.id, app.status])
  const resumes = useAsync(() => listResumes(), [])
  const [notes, setNotes] = useState(app.notes ?? '')
  const [error, setError] = useState<string>()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function save(data: ApplicationUpdate) {
    setError(undefined)
    try {
      onChange(await updateApplication(app.id, data))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    }
  }

  async function remove() {
    if (!window.confirm('Delete this application and its history?')) return
    await deleteApplication(app.id)
    onDelete()
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={app.job_offer.title}>
        <div
          className="row"
          style={{ justifyContent: 'space-between', flexWrap: 'nowrap', alignItems: 'flex-start' }}
        >
          <div>
            <p className="muted small">{app.job_offer.company_name}</p>
            <h2>{app.job_offer.title}</h2>
            <Link to={`/offers/${app.job_offer.id}`} className="small">
              View offer
            </Link>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close">
            <Icon name="x" />
          </button>
        </div>

        <label className="field">
          <span>Status</span>
          <select
            className="select"
            value={app.status}
            onChange={(e) => save({ status: e.target.value as ApplicationStatus })}
          >
            {APPLICATION_STATUSES.map((s) => (
              <option key={s} value={s}>
                {statusLabel[s]}
              </option>
            ))}
          </select>
        </label>

        <div className="grid-2" style={{ gap: 12 }}>
          <label className="field">
            <span>Applied on</span>
            <input
              className="input"
              type="date"
              value={app.applied_at ? toLocalInput(app.applied_at).slice(0, 10) : ''}
              onChange={(e) =>
                save({ applied_at: e.target.value ? new Date(e.target.value).toISOString() : null })
              }
            />
          </label>
          <label className="field">
            <span>Interview</span>
            <input
              className="input"
              type="datetime-local"
              value={toLocalInput(app.interview_at)}
              onChange={(e) =>
                save({
                  interview_at: e.target.value ? new Date(e.target.value).toISOString() : null,
                })
              }
            />
          </label>
        </div>

        <label className="field">
          <span>CV you sent</span>
          <select
            className="select"
            value={app.resume_id ?? ''}
            onChange={(e) => save({ resume_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Not recorded</option>
            {resumes.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Notes</span>
          <textarea
            className="textarea"
            value={notes}
            placeholder="Recruiter name, salary range, questions they asked…"
            onChange={(e) => setNotes(e.target.value)}
            onBlur={() => notes !== (app.notes ?? '') && save({ notes: notes || null })}
          />
          <span className="hint">Saved when you leave the field.</span>
        </label>

        {error && <p className="error-text">{error}</p>}

        <div>
          <h3 style={{ marginBottom: 12 }}>History</h3>
          <ol className="timeline">
            {[...(history.data ?? [])].reverse().map((h) => (
              <li
                key={h.changed_at + h.status}
                style={{ '--dot': statusColor(h.status) } as CSSProperties}
              >
                <div>{statusLabel[h.status]}</div>
                <div className="small muted">
                  {formatDate(h.changed_at)} · {formatTime(h.changed_at)}
                </div>
              </li>
            ))}
          </ol>
        </div>

        <button className="btn btn-danger" onClick={remove} style={{ marginTop: 'auto' }}>
          <Icon name="trash" size={16} /> Delete application
        </button>
      </aside>
    </>
  )
}
