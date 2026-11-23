import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { request, setUnauthorizedHandler, tokenStore } from './client'

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** A fake backend: /me works only with token "new"; /auth/refresh answers `refreshStatus`. */
function backend(refreshStatus = 200) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(url)
    if (url.endsWith('/auth/refresh')) {
      return refreshStatus === 200
        ? json(200, { access_token: 'new', token_type: 'bearer' })
        : json(401, { detail: 'Your login has ended, please log in again' })
    }
    const auth = (init?.headers as Record<string, string>).Authorization
    return auth === 'Bearer new' ? json(200, { email: 'me@example.com' }) : json(401, {})
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

beforeEach(() => tokenStore.set('expired'))
afterEach(() => {
  vi.unstubAllGlobals()
  tokenStore.clear()
  setUnauthorizedHandler(null)
})

describe('request with an expired access token', () => {
  it('gets a new one from the refresh cookie and repeats the request', async () => {
    const calls = backend()

    const me = await request<{ email: string }>('/auth/me')

    expect(me.email).toBe('me@example.com')
    expect(tokenStore.get()).toBe('new')
    expect(calls).toEqual(['/api/auth/me', '/api/auth/refresh', '/api/auth/me'])
  })

  it('refreshes once for requests that fail together', async () => {
    const calls = backend()

    await Promise.all([request('/a'), request('/b'), request('/c')])

    expect(calls.filter((c) => c.endsWith('/auth/refresh'))).toHaveLength(1)
  })

  it('logs out when the refresh cookie no longer works', async () => {
    backend(401)
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)

    await expect(request('/auth/me')).rejects.toThrow()

    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})
