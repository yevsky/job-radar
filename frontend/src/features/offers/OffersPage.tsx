import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import type { EmploymentType, ExperienceLevel } from '@/api/enums'
import { listJobOffers, type JobOfferFilters } from '@/api/jobOffers'
import { Icon } from '@/components/Icon'
import { Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { useAsync } from '@/lib/useAsync'

import { OfferFilters } from './OfferFilters'
import { OfferRow } from './OfferRow'
import { SaveButton } from './SaveButton'

const PAGE_SIZE = 20

/** Filters live in the URL (?technology=Python&location=…&page=2), so a filtered list can be shared. */
function readFilters(params: URLSearchParams): JobOfferFilters {
  return {
    technology: params.getAll('technology'),
    location: params.get('location') ?? '',
    experience_level: params.getAll('experience_level') as ExperienceLevel[],
    employment_type: params.getAll('employment_type') as EmploymentType[],
  }
}

function writeFilters(filters: JobOfferFilters): URLSearchParams {
  const params = new URLSearchParams()
  filters.technology.forEach((t) => params.append('technology', t))
  if (filters.location) params.set('location', filters.location)
  filters.experience_level.forEach((l) => params.append('experience_level', l))
  filters.employment_type.forEach((t) => params.append('employment_type', t))
  return params
}

export function OffersPage() {
  const [params, setParams] = useSearchParams()
  const key = params.toString()
  const filters = useMemo(() => readFilters(new URLSearchParams(key)), [key])
  const page = Math.max(1, Number(params.get('page')) || 1)

  const result = useAsync(
    (signal) => listJobOffers(filters, PAGE_SIZE, (page - 1) * PAGE_SIZE, signal),
    [key],
  )
  const pages = result.data ? Math.max(1, Math.ceil(result.data.total / PAGE_SIZE)) : 1

  function goTo(nextPage: number) {
    const next = new URLSearchParams(params)
    next.set('page', String(nextPage))
    setParams(next)
    window.scrollTo({ top: 0 })
  }

  return (
    <>
      <PageHeader
        icon="list"
        title="Job board"
        lead="Offers posted on the site for everyone. The ones you add yourself or keep from a search are in My offers."
        actions={
          <Link to="/my-offers" className="btn">
            <Icon name="bookmark" size={16} />
            My offers
          </Link>
        }
      />
      <div className="split" style={{ gridTemplateColumns: '280px minmax(0, 1fr)' }}>
        <OfferFilters
          key={filters.location}
          value={filters}
          onChange={(f) => setParams(writeFilters(f))}
        />
        <section className="stack" aria-live="polite">
          {result.data && (
            <p className="muted small">
              {result.data.total} {result.data.total === 1 ? 'offer' : 'offers'}
              {pages > 1 && ` · page ${page} of ${pages}`}
            </p>
          )}
          {result.error && <ErrorBox error={result.error} onRetry={result.reload} />}
          {result.loading && !result.data && <Loading />}
          {result.data?.items.length === 0 && (
            <Empty title="No offers match">Try removing a filter.</Empty>
          )}
          {result.data && result.data.items.length > 0 && (
            <div className="list" style={{ opacity: result.loading ? 0.6 : 1 }}>
              {result.data.items.map((offer) => (
                <OfferRow
                  key={offer.id}
                  offer={offer}
                  aside={<SaveButton offerId={offer.id} compact />}
                />
              ))}
            </div>
          )}
          {pages > 1 && (
            <div className="row" style={{ justifyContent: 'center' }}>
              <button className="btn btn-sm" disabled={page <= 1} onClick={() => goTo(page - 1)}>
                Previous
              </button>
              <span className="small muted">
                {page} / {pages}
              </span>
              <button
                className="btn btn-sm"
                disabled={page >= pages}
                onClick={() => goTo(page + 1)}
              >
                Next
              </button>
            </div>
          )}
        </section>
      </div>
    </>
  )
}
