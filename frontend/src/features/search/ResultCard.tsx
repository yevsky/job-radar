import type { CSSProperties } from 'react'

import type { SearchResult } from '@/api/search'
import { Icon } from '@/components/Icon'
import { employmentLabel, experienceLabel } from '@/lib/labels'

import { formatSalary, isNew, isRemote, monogram, tileColor } from './searchUtils'

export function CompanyTile({ company, size = 64 }: { company: string; size?: number }) {
  return (
    <span
      className="company-tile"
      style={
        {
          '--tile': tileColor(company),
          width: size,
          height: size,
          fontSize: size * 0.34,
        } as CSSProperties
      }
      aria-hidden
    >
      {monogram(company)}
    </span>
  )
}

export function ResultCard({
  result,
  selected,
  compact,
  savedId,
  now,
  onOpen,
  onSave,
}: {
  result: SearchResult
  selected: boolean
  compact: boolean
  savedId: number | undefined
  now: number
  onOpen: () => void
  onSave: () => void
}) {
  const salary = formatSalary(result)
  return (
    <article
      className="result-card"
      data-selected={selected}
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      aria-label={`${result.title} at ${result.company_name}`}
    >
      <CompanyTile company={result.company_name} size={compact ? 56 : 64} />
      <div className="result-main">
        <div className="result-top">
          <div className="result-heading">
            <h3 className="result-title">{result.title}</h3>
            {isNew(result, now) && <span className="tag tag-info">new</span>}
            {savedId && <span className="tag tag-new">saved</span>}
          </div>
          {salary && !compact && <span className="salary">{salary}</span>}
          <button
            className="btn btn-ghost btn-icon"
            aria-label={savedId ? 'Saved to my offers' : 'Save to my offers'}
            title={savedId ? 'Saved to my offers' : 'Save to my offers'}
            onClick={(e) => {
              e.stopPropagation()
              if (!savedId) onSave()
            }}
          >
            <Icon name={savedId ? 'checkCircle' : 'plusCircle'} size={22} />
          </button>
        </div>
        {salary && compact && <span className="salary small">{salary}</span>}
        <div className="result-meta">
          <span>
            <Icon name="building" size={16} /> {result.company_name}
          </span>
          <span>
            <Icon name={isRemote(result) ? 'laptop' : 'location'} size={16} />{' '}
            {result.location ?? 'Not stated'}
          </span>
          {!compact && result.experience_level && (
            <span>
              <Icon name="layers" size={16} /> {experienceLabel[result.experience_level]}
            </span>
          )}
          {!compact && result.employment_type && (
            <span>{employmentLabel[result.employment_type]}</span>
          )}
        </div>
        {result.technologies && result.technologies.length > 0 && (
          <div className="result-techs">
            <Icon name="code" size={16} />
            {result.technologies.map((t) => (
              <span key={t} className="tech">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}
