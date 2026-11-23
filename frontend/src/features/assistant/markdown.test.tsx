import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { Markdown } from './markdown'

afterEach(cleanup)

describe('Markdown', () => {
  it('shows bold, links and lists', () => {
    const { container } = render(
      <Markdown text={'I found:\n\n1. **Junior Dev** at X\n- [View](https://example.com/1)'} />,
    )
    expect(container.querySelector('strong')?.textContent).toBe('Junior Dev')
    expect(container.querySelector('a')?.getAttribute('href')).toBe('https://example.com/1')
    expect(container.querySelectorAll('li')).toHaveLength(2)
  })

  it('keeps HTML from the model as text', () => {
    const { container } = render(
      <Markdown text={'<img src=x onerror=alert(1)> [x](javascript:alert(1))'} />,
    )
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('a')).toBeNull()
  })
})
