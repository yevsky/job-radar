import { Link } from 'react-router-dom'

import { listSavedJobs } from '@/api/savedJobs'
import { DemoBadge, Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { OfferRow } from '@/features/offers/OfferRow'
import { SaveButton } from '@/features/offers/SaveButton'
import { relativeDays } from '@/lib/format'
import { useSavedIds } from '@/lib/savedStore'
import { useAsync } from '@/lib/useAsync'

export function SavedPage() {
  const saved = useAsync(() => listSavedJobs(), [])
  const ids = useSavedIds()
  // Unsaving on this page keeps the row (greyed) until the next visit, so a misclick is easy to undo.
  return (
    <>
      <PageHeader
        icon="bookmark"
        title="Saved offers"
        lead="Offers you saved to look at later. They are also the first column on the Applications board; moving one on means you applied."
        actions={<DemoBadge feature="saved" />}
      />
      {saved.loading && <Loading />}
      {saved.error && <ErrorBox error={saved.error} onRetry={saved.reload} />}
      {saved.data?.length === 0 && (
        <Empty title="Nothing saved yet">
          Use <strong>Save</strong> on any offer, or <Link to="/search">search for jobs</Link>.
        </Empty>
      )}
      {saved.data && saved.data.length > 0 && (
        <div className="list">
          {saved.data.map((s) => (
            <div key={s.id} style={{ opacity: ids && !ids.has(s.job_offer.id) ? 0.5 : 1 }}>
              <OfferRow
                offer={s.job_offer}
                aside={
                  <>
                    <span className="small faint">saved {relativeDays(s.created_at)}</span>
                    <SaveButton offerId={s.job_offer.id} compact />
                  </>
                }
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}
