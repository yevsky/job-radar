/** The CSV columns POST /admin/job-offers/import reads; the first three are required. */
export const CSV_COLUMNS = [
  'title',
  'company_name',
  'url',
  'location',
  'experience_level',
  'employment_type',
  'deadline',
  'technologies',
  'description',
] as const

/** A ready file to fill in: the header and one example line. */
export const CSV_TEMPLATE =
  CSV_COLUMNS.join(',') +
  '\n' +
  'Junior Python Developer,Codesky,https://example.com/jobs/1,Wrocław,junior,full_time,2026-12-31,"Python, FastAPI",Short description\n'

/** Accept only what the backend reads; the size limit is the backend's MAX_IMPORT_BYTES. */
export const MAX_IMPORT_BYTES = 1_000_000

export function checkImportFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!name.endsWith('.json') && !name.endsWith('.csv')) return 'Choose a .json or .csv file'
  if (file.size > MAX_IMPORT_BYTES) return 'The file is larger than 1 MB'
  return null
}
