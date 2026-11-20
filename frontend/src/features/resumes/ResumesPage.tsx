import { useState, type FormEvent } from 'react'

import { getProfile, type ProfileRead } from '@/api/profile'
import {
  applyResume,
  deleteResume,
  listResumes,
  uploadResume,
  type Resume,
  type ResumeApply,
} from '@/api/resumes'
import { Icon } from '@/components/Icon'
import { DemoBadge, Empty, ErrorBox, Loading, PageHeader } from '@/components/ui'
import { formatDate } from '@/lib/format'
import { employmentLabel, experienceLabel } from '@/lib/labels'
import { useAsync } from '@/lib/useAsync'

export function ResumesPage() {
  const resumes = useAsync(() => listResumes(), [])
  const profile = useAsync(() => getProfile(), [])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = resumes.data?.find((r) => r.id === (selectedId ?? resumes.data?.[0]?.id))

  return (
    <>
      <PageHeader
        icon="file"
        title="My CVs"
        lead="Upload a PDF and we read your skills and preferences from it. Only the text is kept, never the file. You choose what goes into your profile."
        actions={<DemoBadge feature="resumes" />}
      />
      {resumes.error && <ErrorBox error={resumes.error} onRetry={resumes.reload} />}
      <div className="split" style={{ gridTemplateColumns: '320px minmax(0, 1fr)' }}>
        <div className="stack">
          <UploadForm
            onUploaded={(r) => {
              resumes.setData((prev) => [r, ...(prev ?? [])])
              setSelectedId(r.id)
            }}
          />
          {resumes.loading && !resumes.data && <Loading />}
          {resumes.data && resumes.data.length > 0 && (
            <div className="list">
              {resumes.data.map((r) => (
                <button
                  key={r.id}
                  className="list-item"
                  style={{
                    border: 0,
                    borderBottom: '1px solid var(--border)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: r.id === selected?.id ? 'var(--surface-2)' : undefined,
                  }}
                  onClick={() => setSelectedId(r.id)}
                  aria-pressed={r.id === selected?.id}
                >
                  <Icon name="file" />
                  <div className="grow">
                    <div className="item-title">{r.label}</div>
                    <div className="small muted">
                      {formatDate(r.created_at)}
                      {r.applied_to_profile_at && ' · used in profile'}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          {resumes.data?.length === 0 && (
            <Empty title="No CVs yet">Upload one to fill your profile in a few clicks.</Empty>
          )}
          {selected && profile.data && (
            <ReviewCard
              key={selected.id}
              resume={selected}
              profile={profile.data}
              onApplied={(p) => {
                profile.setData(p)
                resumes.reload()
              }}
              onDeleted={() => {
                resumes.setData((prev) => (prev ?? []).filter((r) => r.id !== selected.id))
                setSelectedId(null)
              }}
            />
          )}
        </div>
      </div>
    </>
  )
}

function UploadForm({ onUploaded }: { onUploaded: (r: Resume) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(undefined)
    try {
      onUploaded(await uploadResume(file, label.trim()))
      setFile(null)
      setLabel('')
      ;(e.target as HTMLFormElement).reset()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card stack" style={{ padding: 20, gap: 12 }} onSubmit={submit}>
      <h3>Upload a CV</h3>
      <input
        className="input"
        type="file"
        accept="application/pdf,.pdf"
        required
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <input
        className="input"
        placeholder="Name, e.g. Backend CV (English)"
        maxLength={100}
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />
      {error && <p className="error-text">{error}</p>}
      <button className="btn btn-primary" disabled={!file || busy}>
        <Icon name="upload" size={16} /> {busy ? 'Reading your CV…' : 'Upload and read'}
      </button>
    </form>
  )
}

type Field = 'desired_position' | 'experience_level' | 'skills' | 'locations' | 'employment_types'

function ReviewCard({
  resume,
  profile,
  onApplied,
  onDeleted,
}: {
  resume: Resume
  profile: ProfileRead
  onApplied: (p: ProfileRead) => void
  onDeleted: () => void
}) {
  const x = resume.extracted
  const newSkills = x.skills.filter(
    (s) => !profile.skills.some((p) => p.toLowerCase() === s.toLowerCase()),
  )
  const rows: {
    field: Field
    label: string
    fromCv: string
    inProfile: string
    differs: boolean
  }[] = [
    {
      field: 'desired_position',
      label: 'Desired position',
      fromCv: x.desired_position ?? '',
      inProfile: profile.desired_position ?? '',
      differs: !!x.desired_position && x.desired_position !== profile.desired_position,
    },
    {
      field: 'experience_level',
      label: 'Experience level',
      fromCv: x.experience_level ? experienceLabel[x.experience_level] : '',
      inProfile: profile.experience_level ? experienceLabel[profile.experience_level] : '',
      differs: !!x.experience_level && x.experience_level !== profile.experience_level,
    },
    {
      field: 'skills',
      label: 'Skills',
      fromCv: newSkills.length ? `+ ${newSkills.join(', ')}` : x.skills.join(', '),
      inProfile: profile.skills.join(', '),
      differs: newSkills.length > 0,
    },
    {
      field: 'locations',
      label: 'Locations',
      fromCv: x.locations.join(', '),
      inProfile: profile.preferred_locations.join(', '),
      differs: x.locations.length > 0 && x.locations.join() !== profile.preferred_locations.join(),
    },
    {
      field: 'employment_types',
      label: 'Employment types',
      fromCv: x.employment_types.map((t) => employmentLabel[t]).join(', '),
      inProfile: profile.preferred_employment_types.map((t) => employmentLabel[t]).join(', '),
      differs:
        x.employment_types.length > 0 &&
        x.employment_types.join() !== profile.preferred_employment_types.join(),
    },
  ]
  const [picked, setPicked] = useState<Set<Field>>(
    () => new Set(rows.filter((r) => r.differs).map((r) => r.field)),
  )
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string>()

  async function apply() {
    const data: ResumeApply = {}
    if (picked.has('desired_position')) data.desired_position = x.desired_position
    if (picked.has('experience_level')) data.experience_level = x.experience_level
    // Skills are added to the profile, not replaced: nothing the user typed is lost.
    if (picked.has('skills')) data.skills = [...profile.skills, ...newSkills].slice(0, 50)
    if (picked.has('locations')) data.locations = x.locations
    if (picked.has('employment_types')) data.employment_types = x.employment_types
    setBusy(true)
    setError(undefined)
    try {
      onApplied(await applyResume(resume.id, data))
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update the profile')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (
      !window.confirm(
        `Delete "${resume.label}"? Applications that used it will show "Not recorded".`,
      )
    )
      return
    await deleteResume(resume.id)
    onDeleted()
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>{resume.label}</h2>
          <p>
            {resume.file_name} · uploaded {formatDate(resume.created_at)}
            {resume.extracted_with && ` · read by ${resume.extracted_with}`}
          </p>
        </div>
        <button className="btn btn-danger btn-sm" onClick={remove}>
          <Icon name="trash" size={14} /> Delete
        </button>
      </div>
      {x.summary && (
        <p style={{ marginBottom: 20, fontFamily: 'var(--font-heading)', fontSize: '1.1rem' }}>
          “{x.summary}”
        </p>
      )}

      <h3 style={{ marginBottom: 6 }}>Review what we found</h3>
      <p className="muted small" style={{ marginBottom: 10 }}>
        Tick what should go into your profile. Fields that already match are unticked.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="data">
          <thead>
            <tr>
              <th />
              <th>Field</th>
              <th>From the CV</th>
              <th>Your profile now</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.field} style={{ opacity: r.fromCv ? 1 : 0.5 }}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Use ${r.label} from the CV`}
                    disabled={!r.fromCv}
                    checked={picked.has(r.field)}
                    onChange={(e) => {
                      const next = new Set(picked)
                      if (e.target.checked) next.add(r.field)
                      else next.delete(r.field)
                      setPicked(next)
                    }}
                  />
                </td>
                <td className="muted">{r.label}</td>
                <td style={{ fontWeight: r.differs ? 500 : 400 }}>{r.fromCv || '—'}</td>
                <td className="muted">{r.inProfile || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error && (
        <p className="error-text" style={{ marginTop: 12 }}>
          {error}
        </p>
      )}
      <div className="row" style={{ marginTop: 20 }}>
        <button className="btn btn-primary" onClick={apply} disabled={busy || picked.size === 0}>
          {busy ? 'Updating…' : `Apply ${picked.size} to profile`}
        </button>
        {done && (
          <span className="small muted">
            <Icon name="check" size={14} /> Profile updated.
          </span>
        )}
      </div>
    </section>
  )
}
