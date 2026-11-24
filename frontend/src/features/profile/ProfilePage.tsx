import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { EMPLOYMENT_TYPES, EXPERIENCE_LEVELS, type ExperienceLevel } from '@/api/enums'
import * as profileApi from '@/api/profile'
import { listResumes, snapshotResume } from '@/api/resumes'
import type { ProfileRead, ProfileUpdate } from '@/api/profile'
import { getSearchSources, getSearchUsage } from '@/api/search'
import { Icon } from '@/components/Icon'
import { ErrorBox, Loading, PageHeader, TagInput, ToggleChips } from '@/components/ui'
import { CareerSnapshot } from '@/features/resumes/CareerSnapshot'
import { SourcePicker } from '@/features/search/SourcePicker'
import { employmentLabel, experienceLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

import { searchPosition } from './searchPosition'
import { confirmAction } from '@/lib/confirm'

export function ProfilePage() {
  const profile = useAsync(() => profileApi.getProfile(), [])

  return (
    <div className="page-center">
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
      {profile.data && (
        <div className="profile-grid">
          <ProfileForm initial={profile.data} onSaved={profile.setData} />
          <SearchSettings profile={profile.data} />
        </div>
      )}
    </div>
  )
}

/**
 * The user's search settings next to the profile: which sources to ask (saved right away,
 * like on the search page), how many searches are left today and what the search form
 * takes from the profile.
 */
function SearchSettings({ profile }: { profile: ProfileRead }) {
  const sources = useAsync(() => getSearchSources(), [])
  const usage = useAsync(() => getSearchUsage(), [])
  const position = searchPosition(profile)
  const prefill: [string, string][] = [
    ['Position', position || 'not set'],
    ['Skills', profile.skills.slice(0, 10).join(', ') || 'none'],
    ['Cities', profile.preferred_locations.join(', ') || 'none'],
  ]

  return (
    <aside className="stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Your search</h2>
            <p>Where we look for offers and what the search form starts with.</p>
          </div>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          <div className="field">
            <span className="label">Search sources</span>
            {sources.loading && !sources.data && <span className="hint">Loading sources…</span>}
            {sources.error && !sources.data && (
              <span className="hint">{sources.error.message}</span>
            )}
            {sources.data && <SourcePicker data={sources.data} onChange={sources.setData} />}
          </div>
          {usage.data && (
            <div className="field">
              <span className="label">Searches today</span>
              <span>
                {usage.data.left_today} of {usage.data.daily_limit} left
              </span>
            </div>
          )}
          <dl className="prefill">
            {prefill.map(([term, value]) => (
              <div key={term}>
                <dt className="muted small">{term}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <Link to="/search" className="btn">
            <Icon name="search" size={16} /> Find jobs
          </Link>
        </div>
      </section>
    </aside>
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
  const details: (keyof ProfileUpdate)[] = ['experience_level', 'desired_position']
  const dirty = !same(form, initial)

  async function save(e: FormEvent) {
    e.preventDefault()
    setStatus({ kind: 'saving' })
    try {
      let latest = initial
      if (details.some((k) => form[k] !== initial[k])) {
        const blank = (v: string | null) => (v?.trim() ? v.trim() : null)
        latest = await profileApi.updateProfile({
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
    const yes = await confirmAction({
      title: 'Clear your profile?',
      message:
        'Your details, locations, employment types and skills are removed. Your account, CVs and applications stay.',
      confirmLabel: 'Clear profile',
      danger: true,
    })
    if (!yes) return
    await profileApi.deleteProfile()
    const fresh = await profileApi.getProfile()
    onSaved(fresh)
    setForm(fresh)
  }

  return (
    <form className="stack" onSubmit={save}>
      <ProfileSnapshot onUseRole={(role) => set('desired_position', role)} />
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

/**
 * The career snapshot of one CV. One profile per account, but each CV can show the person
 * differently, so the user picks whose snapshot to see: by default the CV last applied to the
 * profile (or the newest with a snapshot). "Use" on a role fills the desired position below;
 * Save keeps it.
 */
function ProfileSnapshot({ onUseRole }: { onUseRole: (role: string) => void }) {
  const resumes = useAsync(() => listResumes(), [])
  const [pickedId, setPickedId] = useState<number | null>(null)
  if (!resumes.data) return null
  const resume =
    resumes.data.find((r) => r.id === pickedId) ?? snapshotResume(resumes.data) ?? resumes.data[0]
  if (!resume) {
    return (
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Career snapshot</h2>
            <p>Upload a CV and the AI sums up your experience, fields and roles to look for.</p>
          </div>
          <Link to="/cvs" className="btn btn-sm">
            <Icon name="upload" size={14} /> Upload a CV
          </Link>
        </div>
      </section>
    )
  }
  const picker = resumes.data.length > 1 && (
    <select
      className="select"
      style={{ width: 'auto' }}
      aria-label="CV whose snapshot to show"
      value={resume.id}
      onChange={(e) => setPickedId(Number(e.target.value))}
    >
      {resumes.data.map((r) => (
        <option key={r.id} value={r.id}>
          {r.label}
          {r.insights ? '' : ' (no snapshot yet)'}
        </option>
      ))}
    </select>
  )
  return (
    <CareerSnapshot
      key={resume.id}
      resume={resume}
      onUseRole={onUseRole}
      picker={picker || undefined}
    />
  )
}
