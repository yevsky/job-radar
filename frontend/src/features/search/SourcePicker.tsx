import { useState } from 'react'

import { setSearchSources, type SearchSources } from '@/api/search'
import { ToggleChips } from '@/components/ui'

import { activeSources } from './searchUtils'

const SOURCE_LABELS: Record<string, string> = {
  tavily: 'Tavily (job boards)',
  jsearch: 'JSearch (Google Jobs)',
  fake: 'Demo source',
}

const sourceLabel = (name: string) => SOURCE_LABELS[name] ?? name

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

  if (available.length === 0) return <span className="hint">No search sources are turned on.</span>

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
    </>
  )
}
