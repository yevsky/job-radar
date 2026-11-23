import { useState } from 'react'
import { Link } from 'react-router-dom'

import { deleteOffer, listImportedOffers, setOfferActive, type AdminOffer } from '@/api/admin'
import { SOURCE_KINDS, type SourceKind } from '@/api/enums'
import { Icon } from '@/components/Icon'
import { Empty, ErrorBox, Loading, PageHeader, Segmented } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { sourceLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

const PAGE_SIZE = 25

type Shown = 'all' | 'active' | 'hidden'
const SHOWN: Record<Shown, boolean | null> = { all: null, active: true, hidden: false }

/** Admin: every public offer, hidden ones too, with hide/show and delete. */
export function AdminOffersPage() {
  const [q, setQ] = useState('')
  const [source, setSource] = useState<SourceKind | ''>('')
  const [shown, setShown] = useState<Shown>('all')
  const [page, setPage] = useState(0)
  const offers = useAsync(
    () =>
      listImportedOffers({
        q: q.trim(),
        source,
        is_active: SHOWN[shown],
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    [q, source, shown, page],
  )
  const pages = Math.max(1, Math.ceil((offers.data?.total ?? 0) / PAGE_SIZE))

  function update(changed: AdminOffer) {
    offers.setData((prev) =>
      prev ? { ...prev, items: prev.items.map((o) => (o.id === changed.id ? changed : o)) } : prev!,
    )
  }

  return (
    <>
      <PageHeader
        icon="list"
        title="Imported offers"
        lead="Public offers everyone can see. Hide one to take it off the list without losing it, or delete it for good. Offers users saved privately are not listed."
        actions={
          <Link className="btn btn-primary" to="/admin/import">
            <Icon name="upload" size={16} />
            Import offers
          </Link>
        }
      />
      <div className="card stack">
        <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
          <input
            className="input"
            type="search"
            placeholder="Title or company"
            aria-label="Find an offer by title or company"
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(0)
            }}
            style={{ maxWidth: 280 }}
          />
          <select
            className="select"
            aria-label="Source"
            value={source}
            onChange={(e) => {
              setSource(e.target.value as SourceKind | '')
              setPage(0)
            }}
            style={{ maxWidth: 200 }}
          >
            <option value="">Every source</option>
            {SOURCE_KINDS.map((s) => (
              <option key={s} value={s}>
                {sourceLabel[s]}
              </option>
            ))}
          </select>
          <Segmented
            label="Shown or hidden"
            value={shown}
            onChange={(v) => {
              setShown(v)
              setPage(0)
            }}
            options={[
              { value: 'all', label: 'All' },
              { value: 'active', label: 'Shown' },
              { value: 'hidden', label: 'Hidden' },
            ]}
          />
        </div>
        {offers.loading && <Loading />}
        {offers.error && <ErrorBox error={offers.error} onRetry={offers.reload} />}
        {offers.data?.items.length === 0 && (
          <Empty title="No offers match">Import a file or change the filters.</Empty>
        )}
        {offers.data && offers.data.items.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Offer</th>
                  <th>Source</th>
                  <th>Added</th>
                  <th title="Users who saved or applied">Tracked by</th>
                  <th>Shown</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {offers.data.items.map((o) => (
                  <OfferRow key={o.id} offer={o} onChange={update} onDeleted={offers.reload} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {offers.data && (
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="small muted">{offers.data.total} offers</span>
            <nav className="row" aria-label="Offer pages" style={{ gap: 8 }}>
              <button
                className="btn btn-sm"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span className="small">
                Page {page + 1} of {pages}
              </span>
              <button
                className="btn btn-sm"
                disabled={page + 1 >= pages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </nav>
          </div>
        )}
      </div>
    </>
  )
}

function OfferRow({
  offer,
  onChange,
  onDeleted,
}: {
  offer: AdminOffer
  onChange: (o: AdminOffer) => void
  onDeleted: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()

  async function run(action: () => Promise<unknown>, after: () => void) {
    setBusy(true)
    setError(undefined)
    try {
      await action()
      after()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  const toggle = () =>
    run(
      () => setOfferActive(offer.id, !offer.is_active),
      () => onChange({ ...offer, is_active: !offer.is_active }),
    )

  const remove = () => {
    const warning =
      offer.saved_by > 0
        ? ` ${offer.saved_by} user(s) track it; their applications for it are deleted too.`
        : ''
    if (!window.confirm(`Delete "${offer.title}" for good?${warning}`)) return
    void run(() => deleteOffer(offer.id), onDeleted)
  }

  return (
    <tr>
      <td style={offer.is_active ? undefined : { opacity: 0.55 }}>
        <a href={offer.url} target="_blank" rel="noreferrer" className="item-title">
          {offer.title}
        </a>
        <div className="small muted">
          {offer.company_name}
          {offer.location && ` · ${offer.location}`}
          {offer.technologies.length > 0 && ` · ${offer.technologies.join(', ')}`}
        </div>
        {error && <div className="error-text">{error}</div>}
      </td>
      <td className="small">
        {sourceLabel[offer.source]}
        {offer.found_via && <span className="muted"> ({offer.found_via})</span>}
      </td>
      <td className="small muted">{formatDate(offer.created_at)}</td>
      <td>{offer.saved_by}</td>
      <td>
        <button
          className="btn btn-sm"
          onClick={() => void toggle()}
          disabled={busy}
          aria-label={`${offer.is_active ? 'Hide' : 'Show'} ${offer.title}`}
        >
          {offer.is_active ? 'Hide' : 'Show'}
        </button>
      </td>
      <td>
        <button
          className="btn btn-sm btn-ghost"
          onClick={remove}
          disabled={busy}
          aria-label={`Delete ${offer.title}`}
          title="Delete for good"
        >
          <Icon name="trash" size={16} />
        </button>
      </td>
    </tr>
  )
}
