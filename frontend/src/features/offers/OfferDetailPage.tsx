import { useNavigate, useParams } from 'react-router-dom'

import { deleteJobOffer, getJobOffer } from '@/api/jobOffers'
import { Icon } from '@/components/Icon'
import { ErrorBox, Loading } from '@/components/ui'
import { MatchCard } from '@/features/match/MatchCard'
import { formatDate, relativeDays } from '@/lib/format'
import { hasOriginal } from '@/lib/originalLink'
import { employmentLabel, experienceLabel, sourceLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

import { TrackPanel } from './TrackPanel'
import { confirmAction } from '@/lib/confirm'

export function OfferDetailPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const offer = useAsync((signal) => getJobOffer(id, signal), [id])

  if (offer.loading && !offer.data) return <Loading />
  if (offer.error) return <ErrorBox error={offer.error} onRetry={offer.reload} />
  const o = offer.data
  if (!o) return null

  async function remove() {
    const yes = await confirmAction({
      title: 'Delete this offer?',
      message: 'Only you can see it, so this removes it for good.',
      confirmLabel: 'Delete',
      danger: true,
    })
    if (!yes) return
    await deleteJobOffer(id)
    navigate('/my-offers')
  }

  const facts: [string, string | null][] = [
    ['Company', o.company_name],
    ['Location', o.location],
    ['Level', o.experience_level && experienceLabel[o.experience_level]],
    ['Type', o.employment_type && employmentLabel[o.employment_type]],
    ['Deadline', o.deadline && `${formatDate(o.deadline)} (${relativeDays(o.deadline)})`],
    ['Source', `${sourceLabel[o.source]}${o.is_private ? ' · only you' : ''}`],
    ['Added', formatDate(o.created_at)],
  ]

  return (
    <>
      <button
        className="btn btn-ghost btn-sm"
        onClick={() => navigate(-1)}
        style={{ marginBottom: 16 }}
      >
        <Icon name="left" size={16} /> Back
      </button>
      <header className="page-header">
        <div>
          <p className="muted">{o.company_name}</p>
          <h1 style={{ marginTop: 6 }}>{o.title}</h1>
          {o.technologies.length > 0 && (
            <div className="row" style={{ gap: 6, marginTop: 14 }}>
              {o.technologies.map((t) => (
                <span className="chip" key={t}>
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="row">
          {hasOriginal(o.url) && (
            <a className="btn" href={o.url} target="_blank" rel="noreferrer noopener">
              Open original <Icon name="external" size={16} />
            </a>
          )}
          {o.is_private && (
            <button className="btn btn-danger" onClick={remove}>
              <Icon name="trash" size={16} /> Delete
            </button>
          )}
        </div>
      </header>

      {!o.is_active && (
        <p className="notice" style={{ marginBottom: 20 }}>
          This offer is hidden from the list.
        </p>
      )}

      <div className="split">
        <div className="stack">
          <MatchCard offerId={o.id} />
          <section className="card">
            <h2 style={{ marginBottom: 14 }}>Description</h2>
            {o.description ? (
              <div style={{ whiteSpace: 'pre-wrap', maxWidth: '70ch' }}>{o.description}</div>
            ) : (
              <p className="muted">
                No description was saved. Open the original posting to read it.
              </p>
            )}
          </section>
        </div>
        <div className="stack">
          <TrackPanel offerId={o.id} />
          <section className="card" style={{ padding: 22 }}>
            <dl
              style={{
                margin: 0,
                display: 'grid',
                gridTemplateColumns: 'auto 1fr',
                gap: '8px 16px',
              }}
            >
              {facts
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k} style={{ display: 'contents' }}>
                    <dt className="muted small">{k}</dt>
                    <dd style={{ margin: 0 }}>{v}</dd>
                  </div>
                ))}
            </dl>
          </section>
        </div>
      </div>
    </>
  )
}
