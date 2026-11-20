import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type { JobOfferListItem } from '@/api/jobOffers'
import { Icon } from '@/components/Icon'
import { formatDate, relativeDays } from '@/lib/format'
import { employmentLabel, experienceLabel } from '@/lib/labels'

/** Deadline in the next 5 days. */
function deadlineIsSoon(deadline: string | null): boolean {
  return !!deadline && new Date(deadline).getTime() - Date.now() < 5 * 86_400_000
}

/** One offer in a list (offers, saved offers). `aside` holds row actions. */
export function OfferRow({ offer, aside }: { offer: JobOfferListItem; aside?: ReactNode }) {
  const soon = deadlineIsSoon(offer.deadline)
  return (
    <div className="list-item">
      <div className="grow">
        <Link to={`/offers/${offer.id}`} className="item-title" style={{ textDecoration: 'none' }}>
          {offer.title}
        </Link>
        <div className="meta">
          <span>{offer.company_name}</span>
          {offer.location && (
            <span className="row" style={{ gap: 4 }}>
              <Icon name="location" size={14} />
              {offer.location}
            </span>
          )}
          {offer.experience_level && <span>{experienceLabel[offer.experience_level]}</span>}
          {offer.employment_type && <span>{employmentLabel[offer.employment_type]}</span>}
          {offer.deadline && (
            <span
              title={formatDate(offer.deadline)}
              style={soon ? { color: 'var(--st-rejected)' } : undefined}
            >
              Deadline {relativeDays(offer.deadline)}
            </span>
          )}
        </div>
        {offer.technologies.length > 0 && (
          <div className="row" style={{ gap: 6, marginTop: 10 }}>
            {offer.technologies.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
      {aside && (
        <div className="row" style={{ alignSelf: 'center' }}>
          {aside}
        </div>
      )}
    </div>
  )
}
