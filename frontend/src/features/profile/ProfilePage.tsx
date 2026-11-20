import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { EMPLOYMENT_TYPES, EXPERIENCE_LEVELS, type ExperienceLevel } from '@/api/enums'
import * as profileApi from '@/api/profile'
import type { ProfileRead, ProfileUpdate } from '@/api/profile'
import { ErrorBox, Loading, PageHeader, TagInput, ToggleChips } from '@/components/ui'
import { employmentLabel, experienceLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

export function ProfilePage() {
  const profile = useAsync(() => profileApi.getProfile(), [])

  return (
    <>
      <PageHeader
        icon="user"
        title="Profile"
        lead="What you're looking for. Search uses these fields to prefill the form, and the match card compares offers against them."
        actions={
          <Link to="/cvs" className="btn">
            Fill from a CV
          </Link>
        }
      />
      {profile.loading && !profile.data && <Loading />}
      {profile.error && <ErrorBox error={profile.error} onRetry={profile.reload} />}
      {profile.data && <ProfileForm initial={profile.data} onSaved={profile.setData} />}
    </>
  )
}

type Status =
  { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string }

/**
 * The backend has one endpoint per part (details, locations, employment types, skills),
 * so Save sends only the parts that changed.
 */
function ProfileForm({
  initial,
  onSaved,
}: {
  initial: ProfileRead
  onSaved: (p: ProfileRead) => void
}) {
  const [form, setForm] = useState(initial)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  const set = <K extends keyof ProfileRead>(key: K, value: ProfileRead[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
  const details: (keyof ProfileUpdate)[] = [
    'first_name',
    'last_name',
    'bio',
    'experience_level',
    'desired_position',
  ]
  const dirty = !same(form, initial)

  async function save(e: FormEvent) {
    e.preventDefault()
    setStatus({ kind: 'saving' })
    try {
      let latest = initial
      if (details.some((k) => form[k] !== initial[k])) {
        const blank = (v: string | null) => (v?.trim() ? v.trim() : null)
        latest = await profileApi.updateProfile({
          first_name: blank(form.first_name),
          last_name: blank(form.last_name),
          bio: blank(form.bio),
          experience_level: form.experience_level,
          desired_position: blank(form.desired_position),
        })
      }
      if (!same(form.preferred_locations, initial.preferred_locations))
        latest = await profileApi.setLocations(form.preferred_locations)
      if (!same(form.preferred_employment_types, initial.preferred_employment_types))
        latest = await profileApi.setEmploymentTypes(form.preferred_employment_types)
      if (!same(form.skills, initial.skills)) latest = await profileApi.setSkills(form.skills)
      onSaved(latest)
      setForm(latest)
      setStatus({ kind: 'saved' })
    } catch (err) {
      setStatus({ kind: 'error', message: err instanceof Error ? err.message : 'Could not save' })
    }
  }

  async function remove() {
    if (!window.confirm('Delete your profile details, locations, employment types and skills?'))
      return
    await profileApi.deleteProfile()
    const fresh = await profileApi.getProfile()
    onSaved(fresh)
    setForm(fresh)
  }

  return (
    <form className="stack" onSubmit={save} style={{ maxWidth: 820 }}>
      <section className="card">
        <div className="card-head">
          <div>
            <h2>About you</h2>
            <p>Name and bio are never sent to search sources.</p>
          </div>
        </div>
        <div className="form-grid">
          <label className="field">
            <span>First name</span>
            <input
              className="input"
              maxLength={120}
              value={form.first_name ?? ''}
              onChange={(e) => set('first_name', e.target.value)}
            />
          </label>
          <label className="field">
            <span>Last name</span>
            <input
              className="input"
              maxLength={120}
              value={form.last_name ?? ''}
              onChange={(e) => set('last_name', e.target.value)}
            />
          </label>
          <label className="field full">
            <span>Bio</span>
            <textarea
              className="textarea"
              maxLength={2000}
              value={form.bio ?? ''}
              onChange={(e) => set('bio', e.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>What you&apos;re looking for</h2>
            <p>Used to prefill search and to score offers.</p>
          </div>
        </div>
        <div className="form-grid">
          <label className="field">
            <span>Desired position</span>
            <input
              className="input"
              maxLength={120}
              placeholder="e.g. Python backend developer"
              value={form.desired_position ?? ''}
              onChange={(e) => set('desired_position', e.target.value)}
            />
          </label>
          <label className="field">
            <span>Experience level</span>
            <select
              className="select"
              value={form.experience_level ?? ''}
              onChange={(e) =>
                set('experience_level', (e.target.value || null) as ExperienceLevel | null)
              }
            >
              <option value="">Not set</option>
              {EXPERIENCE_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {experienceLabel[l]}
                </option>
              ))}
            </select>
          </label>
          <div className="field full">
            <span className="label">Employment types</span>
            <ToggleChips
              options={EMPLOYMENT_TYPES}
              labels={employmentLabel}
              value={form.preferred_employment_types}
              onChange={(v) => set('preferred_employment_types', v)}
            />
          </div>
          <div className="field full">
            <label className="label" htmlFor="locations">
              Preferred locations
            </label>
            <TagInput
              id="locations"
              value={form.preferred_locations}
              onChange={(v) => set('preferred_locations', v)}
              placeholder="Type a city or Remote, then Enter"
              max={10}
            />
          </div>
          <div className="field full">
            <label className="label" htmlFor="skills">
              Skills
            </label>
            <TagInput
              id="skills"
              value={form.skills}
              onChange={(v) => set('skills', v)}
              placeholder="Python, FastAPI, PostgreSQL…"
              max={50}
            />
            <span className="hint">Up to 50. The first 10 are used for search.</span>
          </div>
        </div>
      </section>

      <div className="row">
        <button className="btn btn-primary" disabled={!dirty || status.kind === 'saving'}>
          {status.kind === 'saving' ? 'Saving…' : 'Save profile'}
        </button>
        {dirty && (
          <button type="button" className="btn btn-ghost" onClick={() => setForm(initial)}>
            Discard changes
          </button>
        )}
        {status.kind === 'saved' && !dirty && <span className="muted small">Saved.</span>}
        {status.kind === 'error' && <span className="error-text">{status.message}</span>}
        <span style={{ flex: 1 }} />
        <button type="button" className="btn btn-danger" onClick={remove}>
          Delete profile
        </button>
      </div>
    </form>
  )
}
