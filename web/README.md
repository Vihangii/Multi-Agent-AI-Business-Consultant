# Web frontend (Next.js)

Next.js 16 / React 19 / Tailwind 4 client for the Multi-Agent AI Business
Consultant API. Deploys to Vercel; the FastAPI backend runs elsewhere.

```
Browser ──▶ Next.js (Vercel, static)  ──▶  FastAPI backend (Docker / Render / Railway / VM)
                                             └─ Data Agent → Prophet → OpenAI
```

The browser talks to the API **directly** (`NEXT_PUBLIC_API_URL`). The 25 MB
limit is enforced client-side (`validateFile`) and server-side (413).

**Large files when the API is on Vercel.** Vercel functions reject bodies over
4.5 MB, so when `/health` reports `max_multipart_mb: 4.5` the app uploads
bigger files from the browser to Vercel Blob (`src/lib/blob.ts`, token minted
by `src/app/api/upload/route.ts`) and sends the API a `file_url` instead. This
needs a Blob store connected to the Vercel project (`BLOB_READ_WRITE_TOKEN`).
Without one, files over 4.5 MB get a clear error; smaller files still work.
The blob is deleted when a different file is chosen.

## Features

- CSV / XLSX / XLS upload, 25 MB limit, client + server validation
- Column picker pre-filled from `POST /inspect` auto-detection, with a 5-row preview
- Frequency override (auto / D / W / MS) with per-frequency horizon slider
- Forecast chart: 95% interval band, forecast line, actual markers, crosshair tooltip
- Backtest accuracy: MAPE, MAE, 95% interval coverage, plain-language rating
- Strategic AI report (markdown) with export, plus “Skip AI Recommendations”
- Cleaned-data and forecast tables
- Light/dark theme from the OS, responsive down to phone width

## Local development

```bash
cd web
cp .env.example .env.local        # point NEXT_PUBLIC_API_URL at your backend
npm install
npm run dev                       # http://localhost:3000
```

Start the backend in another terminal (from the repo root):

```bash
uvicorn backend.main:app --reload --port 8000
```

`CORS_ORIGINS` on the backend defaults to `*`, so local dev works out of the box.

## Deploy to Vercel

1. Deploy the backend somewhere public (e.g. `docker compose --profile api up`
   on a VM, or Render/Railway from the repo `Dockerfile` with command
   `uvicorn backend.main:app --host 0.0.0.0 --port 8000`).
   Set `CORS_ORIGINS=https://<your-app>.vercel.app` in its `.env`.
2. In Vercel: **New Project → import this repo → Root Directory: `web`**.
3. Environment variables:
   - `NEXT_PUBLIC_API_URL` = `https://<your-backend-host>`
   - `NEXT_PUBLIC_MAX_UPLOAD_MB` = `25` (optional)
4. (If the API is on Vercel) **Storage → Create Blob store → connect** to this
   project so uploads over 4.5 MB work.
5. Deploy. Vercel auto-detects Next.js; no `vercel.json` is needed.

If the backend has `API_KEY` set, the sidebar shows an API-key field and sends
it as `X-API-Key`. Note that anything the browser sends is visible to the user,
so treat that key as a light gate, not a secret.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | dev server with hot reload |
| `npm run build` | production build (also type-checks) |
| `npm start` | serve the production build |
| `npm run lint` | ESLint |

## Layout

```
src/
  app/            layout, page, global styles (design tokens)
  components/
    ConsultantApp  state, health check, inspect-on-upload, run
    Sidebar        upload, sample CSV, column picker + preview, forecast options, skip-AI, run button
    Results        tabs: dashboard, forecast (+ chart, accuracy), AI report, data
    ForecastChart  Recharts composed chart
    ui             cards, notices, metrics, selects
  app/api/upload   Vercel Blob client-upload token route (+ DELETE cleanup)
  lib/
    api            fetch wrappers for /health, /inspect, /analyze (file or file_url)
    blob           browser → Vercel Blob upload helper
    types          response shapes (mirror the Python side)
    format         money / percent / date formatters
    sample         seeded synthetic sample CSV
```
