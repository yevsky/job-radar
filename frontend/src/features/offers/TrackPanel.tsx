import { useState } from 'react'
import { Link } from 'react-router-dom'

import { createApplication, listApplications, updateApplication } from '@/api/applications'
import { StatusBadge } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { setTracked } from '@/lib/savedStore'
import { useAsync } from '@/lib/useAsync'

import { SaveButton } from './SaveButton'

/** Save / start an application for one offer, and show where that application is now. */
export function TrackPanel({ offerId }: { offerId: number }) {
  const apps = useAsync(() => listApplications(), [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const application = apps.data?.find((a) => a.job_offer.id === offerId)

  async function apply() {
    setBusy(true)
    setError(undefined)
    try {
      // Saving creates an application with status `saved`, so look again before creating one.
      const current = (await listApplications()).find((a) => a.job_offer.id === offerId)
      const next = current
        ? await updateApplication(current.id, { status: 'applied' })
        : await createApplication({ job_offer_id: offerId, status: 'applied' })
      apps.setData((prev) => [...(prev ?? []).filter((a) => a.id !== next.id), next])
      setTracked(offerId, { applicationId: next.id, status: next.status })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card stack" style={{ padding: 22, gap: 14 }}>
      <h3>Track it</h3>
      <div className="row">
        <SaveButton offerId={offerId} />
        {(!application || application.status === 'saved') && (
          <button className="btn btn-primary" onClick={apply} disabled={busy || apps.loading}>
            I applied
          </button>
        )}
      </div>
      {error && <p className="alert">{error}</p>}
      {application && application.status !== 'saved' && (
        <div className="stack" style={{ gap: 6 }}>
          <div className="row">
            <StatusBadge status={application.status} />
            {application.applied_at && (
              <span className="small muted">applied {formatDate(application.applied_at)}</span>
            )}
          </div>
          <Link to={`/applications?open=${application.id}`} className="small">
            Open on the board
          </Link>
        </div>
      )}
    </section>
  )
}
