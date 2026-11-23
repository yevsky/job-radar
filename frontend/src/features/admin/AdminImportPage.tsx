import { useState } from 'react'
import { Link } from 'react-router-dom'

import { importOffers, type ImportReport } from '@/api/admin'
import { Icon } from '@/components/Icon'
import { ErrorBox, PageHeader } from '@/components/ui'

import { CSV_COLUMNS, CSV_TEMPLATE, checkImportFile } from './importTemplate'

/** Admin: upload a JSON or CSV file of public offers and read the import report. */
export function AdminImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error>()
  const [report, setReport] = useState<{ name: string; report: ImportReport }>()

  function choose(next: File | null) {
    setFile(next)
    setProblem(next ? checkImportFile(next) : null)
    setError(undefined)
  }

  async function upload() {
    if (!file || problem) return
    setBusy(true)
    setError(undefined)
    try {
      setReport({ name: file.name, report: await importOffers(file) })
    } catch (err) {
      setError(err instanceof Error ? err : new Error('The import failed'))
    } finally {
      setBusy(false)
    }
  }

  function downloadTemplate() {
    const url = URL.createObjectURL(new Blob([CSV_TEMPLATE], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'job-offers-template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <PageHeader
        icon="upload"
        title="Import offers"
        lead="Add public offers for every user from a JSON or CSV file. An offer whose link is already in the app is updated instead of copied."
        actions={
          <Link className="btn" to="/admin/offers">
            Posted offers
          </Link>
        }
      />
      <div className="grid-2">
        <div className="card stack">
          <div className="card-head">
            <h2>Upload a file</h2>
          </div>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault()
              void upload()
            }}
          >
            <label className="field">
              <span>JSON or CSV file, up to 1 MB and 500 offers</span>
              <input
                className="input"
                type="file"
                accept=".json,.csv,application/json,text/csv"
                onChange={(e) => choose(e.target.files?.[0] ?? null)}
              />
            </label>
            {problem && <p className="error-text">{problem}</p>}
            <div className="row">
              <button className="btn btn-primary" disabled={!file || !!problem || busy}>
                <Icon name="upload" size={16} />
                {busy ? 'Importing…' : 'Import'}
              </button>
            </div>
          </form>
          {error && <ErrorBox error={error} />}
        </div>
        <div className="card stack">
          <div className="card-head">
            <h2>File format</h2>
          </div>
          <p className="small">
            <strong>CSV:</strong> a header row, then one offer per line. Commas or semicolons both
            work. Put several technologies in one cell: <code>Python, FastAPI</code>.
          </p>
          <p className="small muted">
            Columns: {CSV_COLUMNS.map((c, i) => (i < 3 ? `${c} (required)` : c)).join(', ')}
          </p>
          <p className="small">
            <strong>JSON:</strong> a list of objects with the same fields, technologies as a list.
          </p>
          <div className="row">
            <button type="button" className="btn btn-sm" onClick={downloadTemplate}>
              Download a CSV template
            </button>
          </div>
        </div>
      </div>
      {report && <ReportCard name={report.name} report={report.report} />}
    </>
  )
}

export function ReportCard({ name, report }: { name: string; report: ImportReport }) {
  return (
    <section className="card stack" aria-label="Import report" style={{ marginTop: 16 }}>
      <div className="card-head">
        <h2>Import report</h2>
        <p>{name}</p>
      </div>
      <div className="stats">
        <Stat label="Created" value={report.created} />
        <Stat label="Updated" value={report.updated} />
        <Stat label="Repeated in the file" value={report.skipped} />
        <Stat label="Invalid" value={report.errors.length} />
      </div>
      {report.errors.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table className="data">
            <thead>
              <tr>
                <th>Row</th>
                <th>What is wrong</th>
              </tr>
            </thead>
            <tbody>
              {report.errors.map((e) => (
                <tr key={e.row}>
                  <td>{e.row}</td>
                  <td>{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="stat-num">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
