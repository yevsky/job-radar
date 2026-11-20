import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { listApplications, updateApplication, type Application } from '@/api/applications'
import { APPLICATION_STATUSES, type ApplicationStatus } from '@/api/enums'
import { Icon } from '@/components/Icon'
import {
  DemoBadge,
  Empty,
  ErrorBox,
  Loading,
  PageHeader,
  Segmented,
  StatusBadge,
} from '@/components/ui'
import { formatDate, formatShort, relativeDays } from '@/lib/format'
import { employmentLabel, experienceLabel, statusColor, statusLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

import { ApplicationDrawer } from './ApplicationDrawer'

type View = 'board' | 'list'

export function ApplicationsPage() {
  const apps = useAsync(() => listApplications(), [])
  const [params, setParams] = useSearchParams()
  const [view, setView] = useState<View>('board')
  const [error, setError] = useState<Error>()
  const openId = Number(params.get('open')) || null
  const open = apps.data?.find((a) => a.id === openId)

  const setOpen = (id: number | null) =>
    setParams(id ? { open: String(id) } : {}, { replace: true })

  function replace(updated: Application) {
    apps.setData((prev) => (prev ?? []).map((a) => (a.id === updated.id ? updated : a)))
  }

  /** Optimistic: move the card now, roll back if the backend refuses. */
  async function move(app: Application, status: ApplicationStatus) {
    if (app.status === status) return
    setError(undefined)
    replace({ ...app, status })
    try {
      replace(await updateApplication(app.id, { status }))
    } catch (err) {
      replace(app)
      setError(err instanceof Error ? err : new Error(String(err)))
    }
  }

  return (
    <>
      <PageHeader
        icon="board"
        title="Applications"
        lead="Drag a card to change its status, or open it to add notes, dates and the CV you sent."
        actions={
          <>
            <DemoBadge feature="applications" />
            <Segmented
              label="View"
              value={view}
              onChange={setView}
              options={[
                { value: 'board', label: 'Board' },
                { value: 'list', label: 'List' },
              ]}
            />
          </>
        }
      />
      {error && <ErrorBox error={error} />}
      {apps.loading && !apps.data && <Loading />}
      {apps.error && <ErrorBox error={apps.error} onRetry={apps.reload} />}
      {apps.data?.length === 0 && (
        <Empty title="No applications yet">
          Open an <Link to="/offers">offer</Link> and press <strong>I applied</strong>.
        </Empty>
      )}
      {apps.data &&
        apps.data.length > 0 &&
        (view === 'board' ? (
          <Board apps={apps.data} onMove={move} onOpen={setOpen} />
        ) : (
          <ListView apps={apps.data} onOpen={setOpen} />
        ))}
      {open && (
        <ApplicationDrawer
          key={open.id}
          app={open}
          onClose={() => setOpen(null)}
          onChange={replace}
          onDelete={() => {
            apps.setData((prev) => (prev ?? []).filter((a) => a.id !== open.id))
            setOpen(null)
          }}
        />
      )}
    </>
  )
}

const DAY = 86_400_000

/** The application with the soonest upcoming interview gets the highlighted "priority" card. */
function nextInterviewId(apps: Application[], now: number): number | null {
  let best: Application | null = null
  for (const a of apps) {
    if (!a.interview_at || new Date(a.interview_at).getTime() < now) continue
    if (!best || a.interview_at < best.interview_at!) best = a
  }
  return best?.id ?? null
}

function cardTag(app: Application, now: number): { text: string; className: string } | null {
  if (app.interview_at && new Date(app.interview_at).getTime() >= now)
    return { text: `Interview ${relativeDays(app.interview_at)}`, className: 'tag-info' }
  if (app.applied_at && now - new Date(app.applied_at).getTime() < 3 * DAY)
    return { text: 'New', className: 'tag-new' }
  return null
}

function Board({
  apps,
  onMove,
  onOpen,
}: {
  apps: Application[]
  onMove: (app: Application, status: ApplicationStatus) => void
  onOpen: (id: number) => void
}) {
  const [dragging, setDragging] = useState<number | null>(null)
  const [over, setOver] = useState<ApplicationStatus | null>(null)
  const [now] = useState(() => Date.now())
  const priorityId = nextInterviewId(apps, now)

  return (
    <div className="board">
      {APPLICATION_STATUSES.map((status) => {
        const items = apps.filter((a) => a.status === status)
        return (
          <section
            key={status}
            className="column"
            data-over={over === status}
            aria-label={statusLabel[status]}
            onDragOver={(e) => {
              e.preventDefault()
              setOver(status)
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(e) => {
              e.preventDefault()
              setOver(null)
              const app = apps.find((a) => a.id === Number(e.dataTransfer.getData('text/plain')))
              if (app) onMove(app, status)
            }}
          >
            <div className="column-head">
              <span className="dot" style={{ background: statusColor(status) }} />
              <h2>{statusLabel[status]}</h2>
              <span className="muted small">{items.length}</span>
            </div>
            {items.map((app) => {
              const priority = app.id === priorityId
              const tag = priority
                ? { text: 'Next interview', className: 'tag-dark' }
                : cardTag(app, now)
              const o = app.job_offer
              const sub = [
                o.location,
                o.experience_level && experienceLabel[o.experience_level],
                o.employment_type && employmentLabel[o.employment_type],
              ]
                .filter(Boolean)
                .join(' · ')
              return (
                <article
                  key={app.id}
                  className={`app-card${priority ? ' priority' : ''}`}
                  draggable
                  tabIndex={0}
                  aria-grabbed={dragging === app.id}
                  aria-label={`${o.title} at ${o.company_name}`}
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', String(app.id))
                    setDragging(app.id)
                  }}
                  onDragEnd={() => setDragging(null)}
                  onClick={() => onOpen(app.id)}
                  onKeyDown={(e) => e.key === 'Enter' && onOpen(app.id)}
                >
                  <div className="row" style={{ justifyContent: 'space-between', minHeight: 22 }}>
                    {tag ? <span className={`tag ${tag.className}`}>{tag.text}</span> : <span />}
                    <button
                      className="btn btn-ghost btn-icon"
                      style={{ width: 26, height: 26, color: 'inherit' }}
                      aria-label="Open details"
                      onClick={(e) => {
                        e.stopPropagation()
                        onOpen(app.id)
                      }}
                    >
                      <Icon name="more" size={18} />
                    </button>
                  </div>
                  <div>
                    <div className="app-card-title">{o.title}</div>
                    <div className="card-sub row" style={{ gap: 6, marginTop: 4 }}>
                      <Icon name="building" size={14} />
                      {o.company_name}
                    </div>
                  </div>
                  {sub && <div className="card-sub">{sub}</div>}
                  <div className="card-foot">
                    {app.applied_at && (
                      <span title="Applied">
                        <Icon name="calendar" size={15} />
                        {formatShort(app.applied_at)}
                      </span>
                    )}
                    {app.notes && (
                      <span title="Has notes">
                        <Icon name="note" size={15} />
                        Notes
                      </span>
                    )}
                    {app.resume_id && (
                      <span title="CV recorded">
                        <Icon name="file" size={15} />
                        CV
                      </span>
                    )}
                  </div>
                </article>
              )
            })}
          </section>
        )
      })}
    </div>
  )
}

function ListView({ apps, onOpen }: { apps: Application[]; onOpen: (id: number) => void }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data">
        <thead>
          <tr>
            <th>Offer</th>
            <th>Status</th>
            <th>Applied</th>
            <th>Interview</th>
            <th>Last change</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((a) => (
            <tr key={a.id} onClick={() => onOpen(a.id)} style={{ cursor: 'pointer' }}>
              <td>
                <div style={{ fontWeight: 500 }}>{a.job_offer.title}</div>
                <div className="small muted">{a.job_offer.company_name}</div>
              </td>
              <td>
                <StatusBadge status={a.status} />
              </td>
              <td>{formatDate(a.applied_at)}</td>
              <td>{a.interview_at ? formatShort(a.interview_at) : ''}</td>
              <td className="muted">{relativeDays(a.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
