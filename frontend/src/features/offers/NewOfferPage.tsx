import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  EMPLOYMENT_TYPES,
  EXPERIENCE_LEVELS,
  type EmploymentType,
  type ExperienceLevel,
} from '@/api/enums'
import {
  createJobOffer,
  MAX_POSTING_LENGTH,
  MIN_POSTING_LENGTH,
  parseJobOffer,
  type JobOfferCreate,
} from '@/api/jobOffers'
import { PageHeader, TagInput } from '@/components/ui'
import { employmentLabel, experienceLabel } from '@/lib/labels'

import { fillFromDraft, missingFields, parseErrorMessage } from './offerDraft'

const empty: JobOfferCreate = {
  title: '',
  company_name: '',
  url: '',
  location: '',
  experience_level: null,
  employment_type: null,
  deadline: null,
  technologies: [],
  description: '',
}

/** What the paste box says after the AI read the posting. */
interface ReadResult {
  parsedWith: string
  missing: string[]
}

/**
 * POST /job-offers: a private offer only this user sees. A known URL opens the existing offer.
 * The paste box above the form calls POST /job-offers/parse to fill the fields; nothing is
 * saved until the user presses Save offer.
 */
export function NewOfferPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(empty)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [posting, setPosting] = useState('')
  const [reading, setReading] = useState(false)
  const [readError, setReadError] = useState<string>()
  const [readResult, setReadResult] = useState<ReadResult>()
  const set = <K extends keyof JobOfferCreate>(k: K, v: JobOfferCreate[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const postingLength = posting.trim().length
  const tooShort = postingLength < MIN_POSTING_LENGTH

  async function readPosting() {
    const pasted = posting
    setReading(true)
    setReadError(undefined)
    setReadResult(undefined)
    try {
      const draft = await parseJobOffer(pasted)
      setForm((f) => fillFromDraft(f, draft, pasted))
      setReadResult({ parsedWith: draft.parsed_with, missing: missingFields(draft) })
    } catch (err) {
      setReadError(parseErrorMessage(err))
    } finally {
      setReading(false)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(undefined)
    try {
      const offer = await createJobOffer({
        ...form,
        location: form.location || null,
        description: form.description || null,
        deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
      })
      navigate(`/offers/${offer.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the offer')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-center">
      <PageHeader
        icon="plus"
        title="Add an offer"
        lead="Found a posting somewhere else? Save it here to track it. Only you will see it."
      />
      <div className="new-offer-grid">
        <section className="card stack paste-card" aria-labelledby="paste-title">
          <div className="card-head">
            <div>
              <h2 id="paste-title">Paste a posting</h2>
              <p>
                The AI reads it and fills the form for you. Check the fields, then press Save offer.
              </p>
            </div>
          </div>
          <textarea
            className="textarea paste-text"
            aria-label="Posting text"
            maxLength={MAX_POSTING_LENGTH}
            placeholder="Copy the whole posting from the job board and paste it here"
            value={posting}
            onChange={(e) => setPosting(e.target.value)}
          />
          <div className="row">
            <button
              type="button"
              className="btn"
              disabled={reading || tooShort}
              onClick={readPosting}
            >
              {reading ? 'Reading the posting…' : 'Fill the form'}
            </button>
            <span className="hint">
              {reading
                ? 'A local model can take up to a minute.'
                : tooShort
                  ? `At least ${MIN_POSTING_LENGTH} characters (${postingLength} now).`
                  : 'Fields the AI finds replace what is in the form.'}
            </span>
          </div>
          {readError && (
            <p className="alert" role="alert">
              {readError}
            </p>
          )}
          {readResult && (
            <p className="notice" role="status">
              Filled by {readResult.parsedWith}. Check every field before you save.
              {readResult.missing.length > 0 && ` Not found: ${readResult.missing.join(', ')}.`}
            </p>
          )}
        </section>
        <form className="card" onSubmit={submit}>
          <div className="form-grid">
            <label className="field full">
              <span>Link to the posting</span>
              <input
                className="input"
                type="url"
                required
                maxLength={2048}
                placeholder="https://…"
                value={form.url}
                onChange={(e) => set('url', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Job title</span>
              <input
                className="input"
                required
                maxLength={200}
                value={form.title}
                onChange={(e) => set('title', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Company</span>
              <input
                className="input"
                required
                maxLength={200}
                value={form.company_name}
                onChange={(e) => set('company_name', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Location</span>
              <input
                className="input"
                maxLength={100}
                value={form.location ?? ''}
                onChange={(e) => set('location', e.target.value)}
              />
            </label>
            <label className="field">
              <span>Deadline</span>
              <input
                className="input"
                type="date"
                value={form.deadline ?? ''}
                onChange={(e) => set('deadline', e.target.value || null)}
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
                <option value="">Not stated</option>
                {EXPERIENCE_LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {experienceLabel[l]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Employment type</span>
              <select
                className="select"
                value={form.employment_type ?? ''}
                onChange={(e) =>
                  set('employment_type', (e.target.value || null) as EmploymentType | null)
                }
              >
                <option value="">Not stated</option>
                {EMPLOYMENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {employmentLabel[t]}
                  </option>
                ))}
              </select>
            </label>
            <div className="field full">
              <label className="label" htmlFor="techs">
                Technologies
              </label>
              <TagInput
                id="techs"
                value={form.technologies ?? []}
                onChange={(v) => set('technologies', v)}
                placeholder="Type and press Enter"
              />
            </div>
            <label className="field full">
              <span>Description</span>
              <textarea
                className="textarea"
                style={{ minHeight: 180 }}
                maxLength={20000}
                value={form.description ?? ''}
                onChange={(e) => set('description', e.target.value)}
              />
              <span className="hint">Paste the posting text. The AI match uses it.</span>
            </label>
          </div>
          {error && (
            <p className="error-text" style={{ marginTop: 12 }}>
              {error}
            </p>
          )}
          <div className="row" style={{ marginTop: 20 }}>
            <button className="btn btn-primary" disabled={busy}>
              {busy ? 'Saving…' : 'Save offer'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => navigate(-1)}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
