# JobRadar frontend

React 19 + TypeScript + Vite. No UI or chart library: plain CSS with design tokens
(`src/styles/tokens.css`) and hand-drawn SVG charts.

## Run it

```powershell
cd frontend
npm install
copy .env.example .env.local   # optional, defaults are fine
npm run dev                    # http://localhost:5173, talks to FastAPI on :8000
npm run dev:mock               # no backend needed, any login works
```

`npm run build`, `npm run lint`, `npm run format`, `npm run typecheck`.

## How it talks to the backend

- The browser calls `/api/...`; Vite proxies it to `VITE_BACKEND_URL` and strips `/api`.
  Same origin, so FastAPI needs no CORS settings in development.
- Everything goes through `src/api/client.ts`. One file per resource in `src/api/`, with
  TypeScript types that mirror the Pydantic schemas.
- `VITE_API_MODE`:
  - `auto` (default): real backend. Endpoints that are not built yet (`planned()` in the
    API files) fall back to demo data when FastAPI answers 404 "Not Found" or 405. The page
    shows a "Demo data" badge, and switches to real data by itself once the endpoint exists.
  - `mock`: everything is demo data (`src/mocks/`), including login.
  - `real`: no demo data at all.
- The JWT from `POST /auth/login` is kept in localStorage and sent as `Authorization: Bearer`.
  A 401 logs the user out.

## Layout

```
src/
  api/          typed endpoint functions (one file per backend router)
  mocks/        in-memory demo data used by mock mode and missing endpoints
  components/   layout, icons, small shared UI
  features/     one folder per page/feature
  lib/          hooks and formatting helpers
  styles/       tokens (light/dark), base, components
  app/nav.ts    sidebar links
  App.tsx       routes
```
