/** How the API client talks to the backend. Set VITE_API_MODE in .env.local. */
export type ApiMode = 'auto' | 'mock' | 'real'

function readMode(): ApiMode {
  const raw = import.meta.env.VITE_API_MODE
  return raw === 'mock' || raw === 'real' ? raw : 'auto'
}

export const API_MODE: ApiMode = readMode()

/** Vite proxies /api to FastAPI (see vite.config.ts). */
export const API_BASE = '/api'

/** Fake network delay for demo data, so loading states are visible. */
export const MOCK_DELAY_MS = 250
