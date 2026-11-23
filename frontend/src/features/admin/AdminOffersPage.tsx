import { useState } from 'react'
import { Link } from 'react-router-dom'

import { deleteOffer, listImportedOffers, setOfferActive, type AdminOffer } from '@/api/admin'
import { Icon } from '@/components/Icon'
import { Empty, ErrorBox, Loading, PageHeader, Segmented } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { hasOriginal } from '@/lib/originalLink'
import { useAsync } from '@/lib/useAsync'
import { confirmAction } from '@/lib/confirm'

const PAGE_SIZE = 50

type Shown = 'all' | 'active' | 'hidden'
const SHOWN: Record<Shown, boolean | null> = { all: null, active: true, hidden: false }

/** Admin: every public offer, hidden ones too, with hide/show and delete. */
export function AdminOffersPage() {
  const [q, setQ] = useState('')
  const [shown, setShown] = useState<Shown>('all')
  const [page, setPage] = useState(0)
  const offers = useAsync(
    () =>
      listImportedOffers({
        q: q.trim(),
        is_active: SHOWN[shown],
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    [q, shown, page],
  )
  const pages = Math.max(1, Math.ceil((offers.data?.total ?? 0) / PAGE_SIZE))

  function goTo(next: number) {
    setPage(next)
    window.scrollTo({ top: 0 })
  }

  function update(changed: AdminOffer) {
    offers.setData((prev) =>
      prev ? { ...prev, items: prev.items.map((o) => (o.id === changed.id ? changed : o)) } : prev!,
    )
  }

  return (
    <>
      <PageHeader
        icon="list"
        title="Posted offers"
        lead="The offers on the Job board, everyone sees them: the ones you imported and the demo offers. Hide one to take it off the board without losing it, or delete it for good. Offers users added for themselves are not listed."
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
        {offers.data && offers.data.total > PAGE_SIZE && (
          <Pager page={page} pages={pages} total={offers.data.total} onPage={goTo} />
        )}
        {offers.loading && !offers.data && <Loading />}
        {offers.error && <ErrorBox error={offers.error} onRetry={offers.reload} />}
        {offers.data?.items.length === 0 && (
          <Empty title="No offers match">Import a file or change the filters.</Empty>
        )}
        {offers.data && offers.data.items.length > 0 && (
          <div style={{ overflowX: 'auto', opacity: offers.loading ? 0.6 : 1 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Offer</th>
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
        {offers.data && <Pager page={page} pages={pages} total={offers.data.total} onPage={goTo} />}
      </div>
    </>
  )
}

/** "51–100 of 230" with Previous / Next; shown above and below the table. */
function Pager({
  page,
  pages,
  total,
  onPage,
}: {
  page: number
  pages: number
  total: number
  onPage: (page: number) => void
}) {
  const first = total ? page * PAGE_SIZE + 1 : 0
  const last = Math.min(total, (page + 1) * PAGE_SIZE)
  return (
    <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
      <span className="small muted">
        {first}–{last} of {total} {total === 1 ? 'offer' : 'offers'}
      </span>
      {pages > 1 && (
        <nav className="row" aria-label="Offer pages" style={{ gap: 8 }}>
          <button className="btn btn-sm" disabled={page === 0} onClick={() => onPage(page - 1)}>
            Previous
          </button>
          <span className="small">
            Page {page + 1} of {pages}
          </span>
          <button
            className="btn btn-sm"
            disabled={page + 1 >= pages}
            onClick={() => onPage(page + 1)}
          >
            Next
          </button>
        </nav>
      )}
    </div>
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

  const remove = async () => {
    const yes = await confirmAction({
      title: `Delete "${offer.title}"?`,
      message:
        offer.saved_by > 0
          ? `${offer.saved_by} ${offer.saved_by === 1 ? 'user tracks' : 'users track'} it; their applications for it are deleted too. To only take it off the board, hide it instead.`
          : 'It is deleted for good. To only take it off the board, hide it instead.',
      confirmLabel: 'Delete',
      danger: true,
    })
    if (yes) void run(() => deleteOffer(offer.id), onDeleted)
  }

  return (
    <tr>
      <td style={offer.is_active ? undefined : { opacity: 0.55 }}>
        <Link to={`/offers/${offer.id}`} className="item-title">
          {offer.title}
        </Link>
        {hasOriginal(offer.url) && (
          <a
            href={offer.url}
            target="_blank"
            rel="noreferrer noopener"
            className="muted"
            title="Open the original posting"
            aria-label={`Open the original posting of ${offer.title}`}
            style={{ marginLeft: 6, verticalAlign: 'middle' }}
          >
            <Icon name="external" size={14} />
          </a>
        )}
        <div className="small muted">
          {offer.company_name}
          {offer.location && ` · ${offer.location}`}
          {offer.technologies.length > 0 && ` · ${offer.technologies.join(', ')}`}
        </div>
        {error && <div className="error-text">{error}</div>}
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
          onClick={() => void remove()}
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
