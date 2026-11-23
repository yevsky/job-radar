import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ReportCard } from './AdminImportPage'
import { checkImportFile, CSV_COLUMNS, CSV_TEMPLATE } from './importTemplate'

afterEach(cleanup)

describe('checkImportFile', () => {
  it('accepts JSON and CSV files', () => {
    expect(checkImportFile(new File(['[]'], 'offers.json'))).toBeNull()
    expect(checkImportFile(new File(['a'], 'OFFERS.CSV'))).toBeNull()
  })

  it('refuses other files and files over 1 MB', () => {
    expect(checkImportFile(new File(['x'], 'offers.xlsx'))).toMatch(/\.json or \.csv/)
    expect(checkImportFile(new File(['x'.repeat(1_000_001)], 'big.csv'))).toMatch(/1 MB/)
  })
})

describe('CSV template', () => {
  it('starts with the columns the backend reads', () => {
    expect(CSV_TEMPLATE.split('\n')[0]).toBe(CSV_COLUMNS.join(','))
  })
})

describe('ReportCard', () => {
  it('shows the counts and every invalid row', () => {
    render(
      <ReportCard
        name="offers.csv"
        report={{
          created: 3,
          updated: 1,
          skipped: 0,
          errors: [{ row: 4, message: 'company_name: Field required' }],
        }}
      />,
    )

    expect(screen.getByText('Created').previousSibling?.textContent).toBe('3')
    expect(screen.getByText('company_name: Field required')).toBeTruthy()
  })
})
