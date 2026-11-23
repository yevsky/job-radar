import { useEffect, useRef, useState } from 'react'

import {
  getSearchDefaults,
  isEmptyQuery,
  MAX_PAGE,
  runSearch,
  saveSearchResult,
  type HiddenResult,
  type SearchQuery,
  type SearchResponse,
  type SearchResult,
} from '@/api/search'
import { Icon } from '@/components/Icon'
import { DemoBadge, Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { markSaved } from '@/lib/savedStore'
import { useAsync } from '@/lib/useAsync'

import { ResultCard } from './ResultCard'
import { ResultDetail } from './ResultDetail'
import { SearchFilters } from './SearchFilters'

export function SearchPage() {
  const defaults = useAsync(() => getSearchDefaults(), [])
  return (
    <>
      <PageHeader
        icon="search"
        title="Find jobs"
        lead="Filters start from your profile. Only these job fields are sent to search sources, never your name or email. Results aren't stored until you save one."
      />
      {defaults.loading && <Loading />}
      {defaults.error && <ErrorBox error={defaults.error} onRetry={defaults.reload} />}
      {defaults.data && <SearchView initial={defaults.data} />}
    </>
  )
}

/** Which list is shown: the results, or what the filters and the sources left out. */
type View = 'found' | 'hidden'

/** The last search that ran, page by page. Paging reuses its form even if the filters were
 * edited since; pages already fetched are shown again without asking the sources. */
interface Run {
  query: SearchQuery
  pages: Record<number, SearchResponse>
  current: number
}

/** The highest page fetched so far. */
const lastPage = (run: Run) => Math.max(...Object.keys(run.pages).map(Number))

function SearchView({ initial }: { initial: SearchQuery }) {
  const [query, setQuery] = useState(initial)
  const [run, setRun] = useState<Run>()
  const [busy, setBusy] = useState<'search' | 'page' | null>(
    isEmptyQuery(initial) ? null : 'search',
  )
  const [error, setError] = useState<Error>()
  const [view, setView] = useState<View>('found')
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [saved, setSaved] = useState<Record<string, number>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string>()
  const [now] = useState(() => Date.now())
  const topRef = useRef<HTMLElement>(null)

  // Run the profile search once when the page opens, like a job board's front page.
  useEffect(() => {
    if (isEmptyQuery(initial)) return
    runSearch(initial, 1)
      .then((response) => setRun({ query: initial, pages: { 1: response }, current: 1 }))
      .catch((err: unknown) => setError(err instanceof Error ? err : new Error(String(err))))
      .finally(() => setBusy(null))
  }, [initial])

  async function search() {
    setBusy('search')
    setError(undefined)
    setSelectedUrl(null)
    setView('found')
    try {
      setRun({ query, pages: { 1: await runSearch(query, 1) }, current: 1 })
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setBusy(null)
    }
  }

  async function goTo(page: number) {
    if (!run || page < 1) return
    setSelectedUrl(null)
    topRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    if (run.pages[page]) {
      setRun({ ...run, current: page })
      return
    }
    setBusy('page')
    setError(undefined)
    try {
      const response = await runSearch(run.query, page)
      // a link already shown on an earlier page is not shown again
      const known = new Set(
        Object.values(run.pages).flatMap((p) =>
          [...p.results, ...(p.hidden_results ?? [])].map((r) => r.url),
        ),
      )
      const fresh = {
        ...response,
        results: response.results.filter((r) => !known.has(r.url)),
        hidden_results: (response.hidden_results ?? []).filter((r) => !known.has(r.url)),
      }
      setRun({ ...run, pages: { ...run.pages, [page]: fresh }, current: page })
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setBusy(null)
    }
  }

  async function save(result: SearchResult) {
    setSaving(result.url)
    setSaveError(undefined)
    try {
      const offer = await saveSearchResult(result)
      // keeping a result also saves it, so it shows in My offers and as Saved on the offer
      await markSaved(offer.id)
      setSaved((s) => ({ ...s, [result.url]: offer.id }))
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Could not save')
    } finally {
      setSaving(null)
    }
  }

  const response = run?.pages[run.current]
  const found = response?.results ?? []
  const hidden: HiddenResult[] = response?.hidden_results ?? []
  const results: SearchResult[] = view === 'found' ? found : hidden
  const reasonOf = (url: string) => hidden.find((h) => h.url === url)?.hidden_because
  const last = run ? lastPage(run) : 1
  const canNext =
    !!run && run.current < MAX_PAGE && (run.current < last || !!run.pages[last]?.has_more)
  const pageCount = run ? last + (canNext && run.current === last ? 1 : 0) : 0
  const selected = results.find((r) => r.url === selectedUrl)
  const detailMode = !!selected
  const filtersVisible = !detailMode || showFilters

  return (
    <div
      className="search-layout"
      data-mode={detailMode ? 'detail' : 'browse'}
      data-filters={filtersVisible}
    >
      {filtersVisible && (
        <SearchFilters
          query={query}
          onChange={setQuery}
          onSubmit={() => {
            setShowFilters(false)
            void search()
          }}
          onReset={() => setQuery(initial)}
          busy={busy === 'search'}
        />
      )}

      <section className="results" aria-live="polite" ref={topRef}>
        <div className="results-bar">
          <div className="row" role="group" aria-label="Show">
            <button
              className="pill"
              aria-pressed={view === 'found'}
              onClick={() => {
                setView('found')
                setSelectedUrl(null)
              }}
            >
              Show found{response ? ` (${found.length})` : ''}
            </button>
            <button
              className="pill"
              aria-pressed={view === 'hidden'}
              onClick={() => {
                setView('hidden')
                setSelectedUrl(null)
              }}
              title="Offers the sources sent that we left out: lists of offers, closed or expired offers, other cities and levels far from the position"
            >
              Show hidden{response ? ` (${hidden.length})` : ''}
            </button>
          </div>
          {detailMode && (
            <button className="btn btn-sm" onClick={() => setShowFilters(!showFilters)}>
              <Icon name="sliders" size={16} /> {showFilters ? 'Hide filters' : 'Filters'}
            </button>
          )}
        </div>

        {run && response && (
          <div className="row small muted" style={{ justifyContent: 'space-between' }}>
            <span className="row" style={{ gap: 8 }}>
              <strong style={{ color: 'var(--text)' }}>
                {view === 'found'
                  ? `${found.length} offers · page ${run.current}`
                  : `${hidden.length} hidden · page ${run.current}`}
              </strong>
              <DemoBadge feature="search" />
              {view === 'hidden' && (response.hidden ?? 0) > hidden.length && (
                <span title="Rows a source sent without a title or a working link">
                  · {(response.hidden ?? 0) - hidden.length} more couldn&apos;t be read
                </span>
              )}
              {response.searches_left_today !== undefined && (
                <span>· {response.searches_left_today} searches left today</span>
              )}
            </span>
            <span className="sent-query" title={`Sent to the search sources: ${response.query}`}>
              Sent: <code>{response.query}</code>
            </span>
          </div>
        )}

        {error && <ErrorBox error={error} />}
        {response?.errors.map((e, i) => (
          <p key={`${e.source}-${i}`} className="alert">
            {e.source} failed: {e.message}. Results from the other sources are below.
          </p>
        ))}
        {busy && <Loading label="Asking the search sources…" />}
        {!run && busy === null && !error && (
          <Empty title="Start a search">Add a position in the filters.</Empty>
        )}
        {run && busy === null && view === 'hidden' && results.length === 0 && (
          <Empty title="Nothing hidden">Every offer the sources sent on this page is shown.</Empty>
        )}
        {run && busy === null && view === 'found' && results.length === 0 && (
          <Empty title={run.current > 1 ? 'No more offers' : 'Nothing found'}>
            {run.current > 1
              ? 'The sources had nothing new on this page.'
              : 'Try a shorter position, more cities or a wider time range.'}
          </Empty>
        )}

        {busy === null && (
          <div className="stack" style={{ gap: 12 }}>
            {results.map((r) => (
              <ResultCard
                key={r.url}
                result={r}
                selected={r.url === selectedUrl}
                compact={detailMode}
                hiddenBecause={view === 'hidden' ? reasonOf(r.url) : undefined}
                savedId={saved[r.url]}
                now={now}
                onOpen={() => setSelectedUrl(r.url)}
                onSave={() => void save(r)}
              />
            ))}
          </div>
        )}
        {run && pageCount > 1 && (
          <nav className="pager" aria-label="Result pages">
            <button
              className="pill"
              onClick={() => void goTo(run.current - 1)}
              disabled={busy !== null || run.current === 1}
            >
              ← Prev
            </button>
            {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                className="pill"
                aria-current={n === run.current ? 'page' : undefined}
                onClick={() => void goTo(n)}
                disabled={busy !== null}
              >
                {n}
              </button>
            ))}
            <button
              className="pill"
              onClick={() => void goTo(run.current + 1)}
              disabled={busy !== null || !canNext}
            >
              Next →
            </button>
          </nav>
        )}
      </section>

      {selected && (
        <ResultDetail
          key={selected.url}
          result={selected}
          all={results}
          savedId={saved[selected.url]}
          saving={saving === selected.url}
          saveError={saveError}
          now={now}
          onSave={() => void save(selected)}
          onSelect={setSelectedUrl}
          onClose={() => setSelectedUrl(null)}
        />
      )}
    </div>
  )
}
