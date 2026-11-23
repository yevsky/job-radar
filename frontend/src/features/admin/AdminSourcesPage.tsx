import { useState } from 'react'

import { listSourceSwitches, switchSource, type SourceSwitch } from '@/api/admin'
import { Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { formatDate, formatTime } from '@/lib/format'
import { searchSourceLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

const FEATURE_LABELS: Record<string, string> = {
  country: 'country',
  posted_within: 'posted within',
  pages: 'more pages',
}

/**
 * Admin: switch each search source on or off for every user at once.
 * Users keep their own choice on the profile page; a switched-off source is only left out.
 */
export function AdminSourcesPage() {
  const [checked, setChecked] = useState(false)
  const sources = useAsync(() => listSourceSwitches(checked), [checked])

  return (
    <>
      <PageHeader
        icon="globe"
        title="Search sources"
        lead="Switch a source off to leave it out of everyone's searches, for example when its API credits run out. Each user's own choice stays saved and works again once the source is back on."
        actions={
          <button
            className="btn"
            onClick={() => (checked ? sources.reload() : setChecked(true))}
            disabled={sources.loading}
            title="Sends one real request to each source"
          >
            {sources.loading && checked ? 'Checking…' : 'Check that they work'}
          </button>
        }
      />
      {sources.loading && !sources.data && <Loading />}
      {sources.error && <ErrorBox error={sources.error} onRetry={sources.reload} />}
      {sources.data?.length === 0 && (
        <Empty title="No sources">The server has none in SEARCH_SOURCES (backend/.env).</Empty>
      )}
      {sources.data && sources.data.length > 0 && (
        <div className="stack" style={{ gap: 12 }}>
          {sources.data.every((s) => !s.enabled) && (
            <div className="alert" role="alert">
              Every source is off, so nobody can search right now.
            </div>
          )}
          {sources.data.map((s) => (
            <SourceCard
              key={s.name}
              source={s}
              onChange={(next) =>
                sources.setData((prev) =>
                  (prev ?? []).map((p) => (p.name === next.name ? next : p)),
                )
              }
            />
          ))}
        </div>
      )}
    </>
  )
}

function SourceCard({
  source,
  onChange,
}: {
  source: SourceSwitch
  onChange: (next: SourceSwitch) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()

  async function flip() {
    setBusy(true)
    setError(undefined)
    try {
      onChange({ ...(await switchSource(source.name, !source.enabled)), ok: source.ok })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card row" style={{ justifyContent: 'space-between', gap: 16 }}>
      <div className="stack" style={{ gap: 4 }}>
        <h2 style={{ margin: 0 }}>{searchSourceLabel(source.name)}</h2>
        <span className="small muted">
          Uses position and cities
          {source.features.length > 0 &&
            `, plus ${source.features.map((f) => FEATURE_LABELS[f] ?? f).join(', ')}`}
          .{' '}
          {source.updated_at
            ? `Last switched ${formatDate(source.updated_at)}, ${formatTime(source.updated_at)}.`
            : 'Never switched: on by default.'}
        </span>
        {source.ok !== null && (
          <span className={source.ok ? 'small' : 'error-text'}>
            {source.ok ? 'Works: the API answered.' : "Doesn't answer: check its API key."}
          </span>
        )}
        {error && <span className="error-text">{error}</span>}
      </div>
      <label className="check">
        <input
          type="checkbox"
          role="switch"
          checked={source.enabled}
          disabled={busy}
          onChange={() => void flip()}
          aria-label={`${searchSourceLabel(source.name)} for all users`}
        />
        <span>{source.enabled ? 'On for everyone' : 'Off for everyone'}</span>
      </label>
    </section>
  )
}
