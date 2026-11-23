import { useState } from 'react'

import { setSearchSources, type SearchSources } from '@/api/search'
import { ToggleChips } from '@/components/ui'
import { searchSourceLabel as sourceLabel } from '@/lib/labels'

import { activeSources } from './searchUtils'

/**
 * Which search engines to ask: GET/PUT /search/sources. Saved on the account right away,
 * so the choice also applies next time. At least one stays ticked (the backend needs one).
 */
export function SourcePicker({
  data,
  onChange,
}: {
  data: SearchSources
  onChange: (next: SearchSources) => void
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string>()
  const { available } = data
  const labels = Object.fromEntries(available.map((s) => [s, sourceLabel(s)]))

  async function change(next: string[]) {
    if (next.length === 0) return
    const all = available.every((s) => next.includes(s))
    setSaving(true)
    setError(undefined)
    try {
      onChange(await setSearchSources(all ? null : next))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the sources')
    } finally {
      setSaving(false)
    }
  }

  const off = data.turned_off ?? []
  const offNote =
    off.length > 0 ? `Switched off by an admin for now: ${off.map(sourceLabel).join(', ')}.` : null

  if (available.length === 0)
    return (
      <span className="hint">
        An admin switched off every search source for now, so search is paused.
      </span>
    )

  return (
    <>
      <ToggleChips
        options={available}
        labels={labels}
        value={activeSources(data)}
        onChange={(v) => void change(v)}
      />
      <span className="hint">
        {saving ? 'Saving…' : error ? error : 'Saved to your account. Keep at least one.'}
      </span>
      {offNote && <span className="hint">{offNote}</span>}
    </>
  )
}
