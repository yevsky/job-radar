import { useState } from 'react'

import { EMPLOYMENT_TYPES, EXPERIENCE_LEVELS } from '@/api/enums'
import { emptyFilters, type JobOfferFilters } from '@/api/jobOffers'
import { TagInput, ToggleChips } from '@/components/ui'
import { employmentLabel, experienceLabel } from '@/lib/labels'

/** Filter panel for GET /job-offers. Location is applied on Enter/blur, not on every key. */
export function OfferFilters({
  value,
  onChange,
}: {
  value: JobOfferFilters
  onChange: (next: JobOfferFilters) => void
}) {
  const [location, setLocation] = useState(value.location)
  const active =
    value.technology.length +
    value.experience_level.length +
    value.employment_type.length +
    (value.location ? 1 : 0)

  return (
    <aside className="card stack" style={{ padding: 22, gap: 18 }} aria-label="Filters">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3>Filters</h3>
        {active > 0 && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setLocation('')
              onChange(emptyFilters)
            }}
          >
            Clear ({active})
          </button>
        )}
      </div>
      <div className="field">
        <label className="label" htmlFor="f-tech">
          Technologies
        </label>
        <TagInput
          id="f-tech"
          value={value.technology}
          onChange={(technology) => onChange({ ...value, technology })}
          placeholder="Python, React…"
        />
        <span className="hint">Offers must use all of them.</span>
      </div>
      <label className="field">
        <span>Location</span>
        <input
          className="input"
          value={location}
          maxLength={100}
          placeholder="Wrocław, Remote…"
          onChange={(e) => setLocation(e.target.value)}
          onBlur={() => location !== value.location && onChange({ ...value, location })}
          onKeyDown={(e) => e.key === 'Enter' && onChange({ ...value, location })}
        />
      </label>
      <div className="field">
        <span className="label">Experience</span>
        <ToggleChips
          options={EXPERIENCE_LEVELS}
          labels={experienceLabel}
          value={value.experience_level}
          onChange={(experience_level) => onChange({ ...value, experience_level })}
        />
      </div>
      <div className="field">
        <span className="label">Employment type</span>
        <ToggleChips
          options={EMPLOYMENT_TYPES}
          labels={employmentLabel}
          value={value.employment_type}
          onChange={(employment_type) => onChange({ ...value, employment_type })}
        />
      </div>
    </aside>
  )
}
