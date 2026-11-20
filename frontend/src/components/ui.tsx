/** Small shared components. Each one is a few lines so pages stay readable. */
import { useState, type ReactNode } from 'react'

import type { ApplicationStatus } from '@/api/enums'
import { statusColor, statusLabel } from '@/lib/labels'
import { useDemoFeatures } from '@/lib/useDemoFeatures'

import { Icon, type IconName } from './Icon'

export function PageHeader({
  icon,
  title,
  lead,
  actions,
}: {
  icon?: IconName
  title: ReactNode
  lead?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <div className="page-title">
          {icon && <Icon name={icon} size={28} />}
          <h1>{title}</h1>
        </div>
        {lead && <p className="lead">{lead}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden />
      {label}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="alert row" role="alert">
      <Icon name="alert" size={18} />
      <span style={{ flex: 1 }}>{error.message}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  )
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className="badge">
      <span className="dot" style={{ background: statusColor(status) }} />
      {statusLabel[status]}
    </span>
  )
}

/** Shows "Demo data" when a feature's endpoint isn't in the backend yet. */
export function DemoBadge({ feature }: { feature: string }) {
  const features = useDemoFeatures()
  if (!features.includes(feature)) return null
  return (
    <span className="demo-badge" title="The backend doesn't have this endpoint yet">
      Demo data
    </span>
  )
}

/** Text input that turns Enter/comma into chips (skills, locations, technologies). */
export function TagInput({
  value,
  onChange,
  placeholder,
  max,
  id,
}: {
  value: string[]
  onChange: (next: string[]) => void
  placeholder?: string
  max?: number
  id?: string
}) {
  const [draft, setDraft] = useState('')
  const full = max !== undefined && value.length >= max

  function add(raw: string) {
    const text = raw.trim()
    if (!text || full) return
    if (!value.some((v) => v.toLowerCase() === text.toLowerCase())) onChange([...value, text])
    setDraft('')
  }

  return (
    <div className="stack" style={{ gap: 8 }}>
      {value.length > 0 && (
        <div className="row" style={{ gap: 6 }}>
          {value.map((tag) => (
            <span className="chip" key={tag}>
              {tag}
              <button
                type="button"
                aria-label={`Remove ${tag}`}
                onClick={() => onChange(value.filter((t) => t !== tag))}
              >
                <Icon name="x" size={14} />
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        id={id}
        className="input"
        value={draft}
        disabled={full}
        placeholder={full ? `Up to ${max}` : placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            add(draft)
          } else if (e.key === 'Backspace' && !draft && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={() => add(draft)}
      />
    </div>
  )
}

/** Multi-select as toggle chips (employment types, experience levels). */
export function ToggleChips<T extends string>({
  options,
  labels,
  value,
  onChange,
}: {
  options: readonly T[]
  labels: Record<T, string>
  value: T[]
  onChange: (next: T[]) => void
}) {
  return (
    <div className="row" style={{ gap: 6 }}>
      {options.map((option) => {
        const on = value.includes(option)
        return (
          <button
            type="button"
            key={option}
            className="chip chip-toggle"
            aria-pressed={on}
            onClick={() => onChange(on ? value.filter((v) => v !== option) : [...value, option])}
          >
            {labels[option]}
          </button>
        )
      })}
    </div>
  )
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
