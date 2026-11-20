import { useState, type FormEvent, type ReactNode } from 'react'

import {
  COUNTRIES,
  getSearchSources,
  isEmptyQuery,
  MAX_LOCATIONS,
  type PostedWithin,
  type SearchQuery,
} from '@/api/search'
import { Icon, type IconName } from '@/components/Icon'
import { TagInput, ToggleChips } from '@/components/ui'
import { useAsync } from '@/lib/useAsync'

import { SourcePicker } from './SourcePicker'
import { supports } from './searchUtils'

const POSTED: Record<PostedWithin | 'any', string> = {
  any: 'Any time',
  day: '24 hours',
  week: 'Week',
  month: 'Month',
}

/** A filter group that folds away, like the section headers on job boards. */
function Section({
  icon,
  title,
  children,
}: {
  icon: IconName
  title: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <section className="filter-section">
      <button
        type="button"
        className="filter-head"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Icon name={icon} size={18} />
        <span>{title}</span>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} size={18} />
      </button>
      {open && <div className="filter-body">{children}</div>}
    </section>
  )
}

/** Why a field is greyed out: none of the chosen engines uses it. */
const offHint = (field: string) => `None of the chosen engines filters by ${field}.`

/** The search form as a filter column. Only these job fields leave the server. */
export function SearchFilters({
  query,
  onChange,
  onSubmit,
  onReset,
  busy,
}: {
  query: SearchQuery
  onChange: (q: SearchQuery) => void
  onSubmit: () => void
  onReset: () => void
  busy: boolean
}) {
  const sources = useAsync(() => getSearchSources(), [])
  const set = <K extends keyof SearchQuery>(k: K, v: SearchQuery[K]) =>
    onChange({ ...query, [k]: v })
  const empty = isEmptyQuery(query)
  const countryOn = supports(sources.data, 'country')
  const postedOn = supports(sources.data, 'posted_within')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!empty) onSubmit()
  }

  return (
    <form className="filters" onSubmit={submit} aria-label="Search filters">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2>Filters</h2>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onReset}>
          Reset to profile
        </button>
      </div>

      <Section icon="globe" title="Search engines">
        {sources.loading && !sources.data && <span className="hint">Loading sources…</span>}
        {sources.error && !sources.data && <span className="hint">{sources.error.message}</span>}
        {sources.data && <SourcePicker data={sources.data} onChange={sources.setData} />}
      </Section>

      <Section icon="briefcase" title="Position">
        <input
          className="input"
          maxLength={120}
          placeholder="e.g. Junior Python developer"
          value={query.position ?? ''}
          onChange={(e) => set('position', e.target.value || null)}
          aria-label="Position"
        />
        <span className="hint">
          Write the level in the name (Junior, Mid, Senior). Offers far from it are hidden.
        </span>
      </Section>

      <Section icon="location" title="City">
        <TagInput
          value={query.locations}
          onChange={(v) => set('locations', v)}
          max={MAX_LOCATIONS}
          placeholder="Add a city"
        />
        <span className="hint">
          Offers from other cities are hidden. Add “Remote” to also see remote offers.
        </span>
      </Section>

      <Section icon="globe" title="Country">
        <select
          className="input"
          value={query.country}
          onChange={(e) => set('country', e.target.value)}
          disabled={!countryOn}
          aria-label="Country"
        >
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
          {!COUNTRIES.some((c) => c.code === query.country) && (
            <option value={query.country}>{query.country.toUpperCase()}</option>
          )}
        </select>
        {!countryOn && <span className="hint">{offHint('country')}</span>}
      </Section>

      <Section icon="clock" title="Posted within">
        <fieldset disabled={!postedOn} className="plain-fieldset">
          <ToggleChips
            options={['any', 'day', 'week', 'month'] as const}
            labels={POSTED}
            value={[query.posted_within ?? 'any']}
            onChange={(v) => {
              const picked = v.find((x) => x !== (query.posted_within ?? 'any')) ?? 'any'
              set('posted_within', picked === 'any' ? null : picked)
            }}
          />
        </fieldset>
        {!postedOn && <span className="hint">{offHint('date')}</span>}
      </Section>

      <div className="filters-foot">
        <button className="btn btn-primary btn-block" disabled={busy || empty}>
          <Icon name="search" size={16} /> {busy ? 'Searching…' : 'Search'}
        </button>
        {empty && <span className="hint">Add a position to search for.</span>}
      </div>
    </form>
  )
}
