import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { listMyOffers, type MyOffer } from '@/api/jobOffers'
import { Icon, type IconName } from '@/components/Icon'
import { Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { OfferRow } from '@/features/offers/OfferRow'
import { SaveButton } from '@/features/offers/SaveButton'
import { relativeDays } from '@/lib/format'
import { searchSourceLabel } from '@/lib/labels'
import { useTracked } from '@/lib/savedStore'
import { useAsync } from '@/lib/useAsync'

import { TABS, countByTab, inTab, type Tab } from './tabs'

/** Where the offer came from, as the row shows it. */
function origin(offer: MyOffer): { icon: IconName; text: string } {
  if (!offer.is_private) return { icon: 'list', text: 'Job board' }
  if (offer.source === 'search')
    return {
      icon: 'search',
      text: offer.found_via ? `Search · ${searchSourceLabel(offer.found_via)}` : 'Search',
    }
  if (offer.source === 'browser') return { icon: 'globe', text: 'From the browser' }
  return { icon: 'pencil', text: 'Added by you' }
}

const EMPTY_TEXT: Record<Tab, string> = {
  all: 'Nothing here yet.',
  saved: 'No saved offers.',
  applied: 'No applications yet.',
  manual: 'You have not added an offer by hand yet.',
  search: 'No offers kept from a search yet.',
}

export function MyOffersPage() {
  const offers = useAsync((signal) => listMyOffers(signal), [])
  const tracked = useTracked()
  const [params, setParams] = useSearchParams()
  const tab = (TABS.find((t) => t.value === params.get('tab'))?.value ?? 'all') as Tab
  const [query, setQuery] = useState('')

  const all = offers.data ?? []
  const counts = countByTab(all)
  const text = query.trim().toLowerCase()
  const shown = all.filter(
    (o) => inTab(o, tab) && (!text || `${o.title} ${o.company_name}`.toLowerCase().includes(text)),
  )

  function pick(next: Tab) {
    const p = new URLSearchParams(params)
    if (next === 'all') p.delete('tab')
    else p.set('tab', next)
    setParams(p, { replace: true })
  }

  return (
    <>
      <PageHeader
        icon="bookmark"
        title="My offers"
        lead="Everything you keep track of: job board offers you saved or applied to, and offers you added by hand or kept from a search. Only you see the ones you added."
        actions={
          <Link to="/offers/new" className="btn btn-primary">
            <Icon name="plus" size={16} />
            Add an offer
          </Link>
        }
      />

      <div className="stack">
        <div className="my-offers-bar">
          <div className="segmented" role="group" aria-label="Show">
            {TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                aria-pressed={t.value === tab}
                onClick={() => pick(t.value)}
              >
                {t.label}
                <span className="count">{counts[t.value]}</span>
              </button>
            ))}
          </div>
          <input
            className="input"
            type="search"
            placeholder="Title or company"
            aria-label="Find one of your offers by title or company"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: 240 }}
          />
        </div>

        {offers.loading && !offers.data && <Loading />}
        {offers.error && <ErrorBox error={offers.error} onRetry={offers.reload} />}

        {offers.data && all.length === 0 && (
          <Empty title="Nothing here yet">
            Save an offer on the <Link to="/offers">Job board</Link>,{' '}
            <Link to="/search">search for jobs</Link> or <Link to="/offers/new">add one</Link>{' '}
            yourself.
          </Empty>
        )}
        {offers.data && all.length > 0 && shown.length === 0 && (
          <Empty title={text ? 'No offer matches' : EMPTY_TEXT[tab]}>
            {text ? 'Try another title or company.' : null}
          </Empty>
        )}

        {shown.length > 0 && (
          <div className="list">
            {shown.map((o) => {
              const from = origin(o)
              // A job board offer you unsave stays (greyed) until the next visit, so a
              // misclick is easy to undo. An offer you added is deleted when you unsave it
              // (after a question), so its row goes at once.
              const dropped = !o.is_private && tracked !== null && !tracked.has(o.id)
              return (
                <div key={o.id} style={{ opacity: dropped ? 0.5 : 1 }}>
                  <OfferRow
                    offer={o}
                    aside={
                      <>
                        <span className="origin" title={`Added ${relativeDays(o.added_at)}`}>
                          <Icon name={from.icon} size={14} />
                          {from.text}
                          {!o.is_active && <span className="chip">hidden</span>}
                        </span>
                        <SaveButton
                          offerId={o.id}
                          compact
                          isPrivate={o.is_private}
                          onDeleted={() =>
                            offers.setData((prev) => (prev ?? []).filter((x) => x.id !== o.id))
                          }
                        />
                      </>
                    }
                  />
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
