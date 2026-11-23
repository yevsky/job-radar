/**
 * The one place that calls fetch().
 *
 * Every endpoint function in src/api/ goes through `request()` (real backend) and, for
 * endpoints the backend doesn't have yet, through `planned()` which falls back to demo data.
 */
import { API_BASE, API_MODE, MOCK_DELAY_MS } from './config'
import { markDemo } from './demoTracker'

const TOKEN_KEY = 'jobradar.token'

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

/** FastAPI error body: `detail` is a string, or a list of validation errors (422). */
interface FastApiValidationError {
  loc: (string | number)[]
  msg: string
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(ApiError.describe(status, detail))
    this.status = status
    this.detail = detail
  }

  /** FastAPI answers {"detail": "Not Found"} (404) or 405 for a route that doesn't exist. */
  get isMissingRoute(): boolean {
    return (this.status === 404 && this.detail === 'Not Found') || this.status === 405
  }

  private static describe(status: number, detail: unknown): string {
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return (detail as FastApiValidationError[])
        .map((e) => `${e.loc.filter((p) => p !== 'body').join('.')}: ${e.msg}`)
        .join('; ')
    }
    return `Request failed (${status})`
  }
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Query
  /** JSON body (objects) or a ready body (FormData, URLSearchParams). */
  body?: unknown
  signal?: AbortSignal
}

/** Build `?a=1&b=x&b=y` the way FastAPI reads list params (repeated keys). */
export function toQueryString(query: Query = {}): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)))
    else params.append(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

/** Called on 401 so the auth context can log the user out. */
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

/**
 * Staying logged in: the access token lasts 30 minutes, the HttpOnly refresh cookie 30 days.
 * When the backend answers 401, we ask POST /auth/refresh for a new access token (the browser
 * sends the cookie by itself) and repeat the request once. Requests that fail together share
 * one refresh, because each refresh token works only once.
 */
let refreshing: Promise<string | null> | null = null

export function refreshAccessToken(): Promise<string | null> {
  if (API_MODE === 'mock') return Promise.resolve(null)
  refreshing ??= fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  })
    .then(async (response) => {
      if (!response.ok) return null
      const data = (await response.json()) as { access_token: string }
      tokenStore.set(data.access_token)
      return data.access_token
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

/** Login, refresh and logout answer 401 for their own reasons: never refresh for them. */
const NO_REFRESH = ['/auth/login', '/auth/refresh', '/auth/logout']

export async function request<T>(
  path: string,
  options: RequestOptions = {},
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (options.body instanceof FormData || options.body instanceof URLSearchParams) {
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const response = await fetch(`${API_BASE}${path}${toQueryString(options.query)}`, {
    method: options.method ?? 'GET',
    headers,
    body,
    signal: options.signal,
  })

  if (response.status === 204) return undefined as T

  const data: unknown = await response.json().catch(() => null)
  if (response.status === 401 && token && !retried && !NO_REFRESH.includes(path)) {
    if (await refreshAccessToken()) return request<T>(path, options, true)
  }
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized?.()
    const detail = data && typeof data === 'object' && 'detail' in data ? data.detail : data
    throw new ApiError(response.status, detail)
  }
  return data as T
}

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY_MS))
}

/**
 * For endpoints the backend already has. In mock mode the demo version is used instead,
 * so the whole UI can run without a backend.
 */
export async function existing<T>(real: () => Promise<T>, mock: () => T | Promise<T>): Promise<T> {
  if (API_MODE === 'mock') return delay(await mock())
  return real()
}

/**
 * For endpoints the backend doesn't have yet. In auto mode we try the backend first and use
 * demo data only if the route is missing (404 "Not Found" / 405), so the page starts using real
 * data the moment Yevhen merges the endpoint, with no frontend change.
 */
export async function planned<T>(
  feature: string,
  real: () => Promise<T>,
  mock: () => T | Promise<T>,
): Promise<T> {
  if (API_MODE === 'mock') {
    markDemo(feature)
    return delay(await mock())
  }
  if (API_MODE === 'real') return real()
  try {
    return await real()
  } catch (err) {
    if (err instanceof ApiError && err.isMissingRoute) {
      markDemo(feature)
      return delay(await mock())
    }
    throw err
  }
}
