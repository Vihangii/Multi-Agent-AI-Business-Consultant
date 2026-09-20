# Multi-Agent AI Business Consultant

Upload a sales/revenue spreadsheet and get back a cleaned dataset, a Prophet
revenue forecast with what-if scenarios, and an LLM-written, fact-checked
strategy report — exportable as PDF or PowerPoint, and re-runnable monthly by email.

```
CSV / Excel ─▶ Data Agent ─▶ Forecast Agent ─▶ Anomaly Agent ─▶ Strategist Agent ─▶ Critic Agent ─▶ Web app
               (pandas)       (Prophet)         (residual z)     (LLM + tools)       (LLM QA)        (Next.js)
```

| Part | Module | What it does |
|---|---|---|
| 1. Data Agent | `backend/agents/data_agent.py` | Detects the date and revenue columns (whole-word, priority-ranked matching), parses currency strings, aggregates duplicate dates, computes growth / monthly / volatility stats, carries an optional driver column |
| 2. Forecast Agent | `backend/agents/forecast_agent.py` | Auto-detects daily / weekly / monthly granularity, fits Prophet (optionally with a driver column as a regressor), returns a ~6-month forecast with 95% intervals, backtests itself (MAPE / MAE / coverage) and precomputes what-if scenarios |
| 3. Anomaly Agent | `backend/agents/anomaly_agent.py` | Robust z-scores on Prophet residuals flag days that collapsed or spiked; month-over-month shocks are flagged too. Fed to the strategist as "explain or exclude?" |
| 4. Strategist Agent | `backend/agents/recommendation_agent.py` + `strategist_tools.py` | Tool-using LLM: calls `get_monthly_breakdown`, `get_top_periods`, `compare_periods`, `get_weekday_profile`, `get_anomalies`, `what_if` to query the data, then writes the report in the requested language. Falls back to a single static prompt for models without tool support |
| 5. Critic Agent | `backend/agents/critic_agent.py` | Second LLM pass: audits every figure in the report against a facts sheet ("claimed 12% growth; data says 8.7%"), rewrites wrong claims, and reports the corrections. Never blocks delivery |
| LLM providers | `backend/llm.py` | One interface, three providers: OpenAI, Anthropic (Claude), Ollama (local). `LLM_PROVIDER=auto` picks whichever has credentials |
| Orchestrator | `backend/orchestrator.py` | Runs the stages and packages the result; an LLM failure never fails the run |
| API | `backend/main.py` | `GET /health`, `GET /metrics`, `POST /inspect`, `POST /analyze` |
| Observability | `backend/observability.py` | Request ids + access log (text/JSON), Prometheus metrics, rate limiting, optional Sentry |
| Vercel entry | `api/index.py` | The same FastAPI app as a Vercel serverless function |
| Web app | `web/` | Next.js UI: column & driver picker, forecast chart, accuracy, what-if slider, AI report, PDF/PPTX export, monthly email schedule |

## Features

- **Upload** CSV / XLSX / XLS up to 25 MB; columns auto-detected and overridable, 5-row preview
- **Forecast** with Prophet; frequency override (auto / D / W / MS) and horizon slider
- **Backtest accuracy**: MAPE, MAE, 95% interval coverage, plain-language rating
- **What-if scenarios**: pick a numeric driver column (e.g. `marketing_spend`); the model is fit with it as a Prophet regressor and re-predicted at −30…+50% so a slider shows the learned revenue response. Without a driver, scenarios are a labelled plain uplift
- **Anomaly detection** on model residuals, shown on the chart and in a table, and handed to the strategist
- **Tool-using strategist**: the LLM queries the data (monthly breakdown, comparisons, weekday profile, what-if) before writing; every tool call is shown as an "agent activity" trace
- **Critic / QA pass**: a second model checks every number against the data and corrects the report; corrections are listed in the UI and noted in exports
- **Provider choice**: OpenAI, Anthropic Claude, or a local Ollama model — swap with one env var, demo fully offline
- **AI strategy report** in 14 languages, with "Skip AI Recommendations" for offline use
- **Export** the whole analysis as **PDF** (vector chart) or **PowerPoint** (native editable chart), or the report as Markdown
- **Monthly email**: schedule a re-run on the 1st of each month via Vercel Cron + Resend, with unsubscribe links
- **Observability**: `/metrics` (Prometheus), structured logs with request ids, `RATE_LIMIT_PER_MINUTE` on `/analyze`, `SENTRY_DSN`
- Optional `X-API-Key` auth, configurable CORS, allow-listed `file_url` ingestion for large uploads

## Requirements

- Python **3.12** (3.13/3.14 don't yet have wheels for the pinned Prophet/NumPy)
- Node **20+** for the web app
- An LLM — **optional**: an OpenAI or Anthropic API key, or a local
  [Ollama](https://ollama.com) model (`OLLAMA_MODEL=llama3.1`) for a fully
  offline demo. Without one, stages 1–3 still run; tick *Skip AI
  Recommendations* in the UI or pass `skip_recommendations=true`.

## Quick start

```powershell
# Windows — creates the venv and .env if missing, starts API + web app in two windows
.\run.ps1
```

```bash
# macOS / Linux
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # add OPENAI_API_KEY
uvicorn backend.main:app --reload --port 8000     # terminal 1

cd web && cp .env.example .env.local && npm install
npm run dev                                       # terminal 2 → http://localhost:3000
```

```bash
# Docker — both services
cp .env.example .env
docker compose up --build                 # API :8000, web :3000
```

Open the web app, download the sample CSV from the sidebar (or upload your
own), and click **Run Consultant Pipeline**.

## Configuration

Backend (`.env`, see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` (anthropic, then openai, then ollama by available credentials), `openai`, `anthropic` or `ollama` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | – / `gpt-4o-mini` | OpenAI credentials and model |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | – / `claude-opus-5` | Anthropic credentials and model |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / – | Local Ollama server and model (set the model to enable) |
| `STRATEGIST_MODE` | `tools` | `tools` (function-calling agent) or `static` (single prompt) |
| `AGENT_MAX_TOOL_ROUNDS` | `6` | Cap on tool-calling rounds before the agent must answer |
| `CRITIC_ENABLED` | `true` | Run the fact-checking pass |
| `BACKEND_HOST` / `BACKEND_PORT` | `0.0.0.0` / `8000` | Where uvicorn listens |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `API_KEY` | – | When set, `/analyze` and `/inspect` require an `X-API-Key` header |
| `FILE_URL_ALLOWED_HOSTS` | `*.public.blob.vercel-storage.com` | Hosts `file_url` inputs may be fetched from |
| `RATE_LIMIT_PER_MINUTE` | `10` | Per-client limit on `POST /analyze` (0 = off) |
| `LOG_FORMAT` | `text` | `json` for one-object-per-line logs |
| `SENTRY_DSN` | – | Enables Sentry error tracking |

Web app (`web/.env.local`, see `web/.env.example`):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Where the browser finds the API |
| `NEXT_PUBLIC_MAX_UPLOAD_MB` | Client-side cap (keep equal to `MAX_UPLOAD_MB`) |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob — needed for uploads > 4.5 MB on Vercel and for scheduling |
| `RESEND_API_KEY`, `EMAIL_FROM` | Resend — needed for monthly emails |
| `CRON_SECRET` | Protects `/api/cron/monthly`; signs unsubscribe links |
| `API_URL`, `API_KEY`, `APP_URL` | Used by the cron job (server-side) |

## Deploy

### Web app → Vercel

Import the repo with **Root Directory `web`**, set `NEXT_PUBLIC_API_URL`, and
(for large uploads + scheduling) attach a **Blob store** and set
`RESEND_API_KEY` / `EMAIL_FROM`. `web/vercel.json` registers the monthly cron.
Full steps in [web/README.md](web/README.md).

### API → Docker host (Render, Railway, Fly, a VM)

Build from the root `Dockerfile`; set `OPENAI_API_KEY` and
`CORS_ORIGINS=https://<your-web-app>.vercel.app`. This is the most proven path.

### API → Vercel Python function

`api/index.py` exports the FastAPI app; `vercel.json` routes every path to it,
so `/health`, `/inspect`, `/analyze`, `/metrics` and `/docs` are served by
**one** Python function.

1. Vercel → **New Project** → import this repo → Root Directory: **`/`**.
2. Environment variables: `PIP_COMPILE=0` (**required** — keeps the bundle
   at ~203 MB instead of ~260 MB against Vercel's 250 MB limit), `OPENAI_API_KEY`,
   `CORS_ORIGINS`, optional `API_KEY`.
3. Deploy. `/health` should report `"platform": "vercel"`.

**Uploads over 4.5 MB.** Vercel rejects request bodies above 4.5 MB before the
function runs, so the API also accepts `file_url` (form field or query param),
downloads the file itself from an allow-listed host, and enforces `MAX_UPLOAD_MB`.
The web app switches to this automatically when `/health` reports
`max_multipart_mb: 4.5`, uploading the file from the browser to Vercel Blob.

Notes: Prophet's optional matplotlib dependency is satisfied by an empty stub
wheel (`vendor/`) to keep ~90 MB out of the bundle; `maxDuration` is 60 s;
CI has a `vercel-bundle` job that fails if the bundle passes 240 MB. In-process
metrics and rate limits are per function instance on Vercel.

## API

```bash
# What would be detected? (columns, numeric driver candidates, preview)
curl -F "file=@sales.csv" http://localhost:8000/inspect

# Run the pipeline
curl -F "file=@sales.csv" "http://localhost:8000/analyze?periods=90&frequency=D&skip_recommendations=true"

# With a what-if driver, Spanish report, explicit columns and an API key
curl -H "X-API-Key: $API_KEY" -F "file=@sales.csv" \
  "http://localhost:8000/analyze?date_column=OrderDate&revenue_column=Total&regressor_column=marketing_spend&language=Spanish"

# Large file already in Blob storage
curl -F "file_url=https://xyz.public.blob.vercel-storage.com/sales.csv" http://localhost:8000/analyze

# Prometheus metrics
curl http://localhost:8000/metrics
```

`/analyze` query parameters: `periods` (2–1000), `frequency` (`D`/`W`/`MS`),
`skip_recommendations`, `date_column`, `revenue_column`, `regressor_column`,
`language`.

The response contains `columns`, `analysis`, `forecast_summary` (with
`accuracy`), `forecast`, `whatif` (scenario table), `anomalies` (points,
periods, summary), `cleaned_data`, and either `recommendations` (markdown) plus
`agent` (provider, model, mode, `tool_calls` trace, `qa` with the critic's
corrections and the `original_report` if it was rewritten) or
`recommendations_error`. An LLM failure never fails the request. Every
response carries an `X-Request-ID` header.

### How the agents work together

1. **Anomaly Agent** compares each historical point with Prophet's in-sample
   prediction; |robust z| >= 3.5 is flagged, >= 5 is "high".
2. **Strategist Agent** receives the summary and the anomalies, then decides
   for itself which tools to call (a typical run: monthly breakdown, anomalies,
   weekday profile, what-if). Each call is executed against the cleaned data
   and returned as JSON; up to `AGENT_MAX_TOOL_ROUNDS` rounds, after which it
   must write the report.
3. **Critic Agent** gets the report plus a facts sheet (all computed figures,
   scenarios, anomalies, monthly revenue) and returns `{issues, revised_report}`.
   Rounding is tolerated; contradictions are rewritten. A truncated or
   unparseable rewrite keeps the original and marks the QA as unverified.

Every provider goes through the same neutral message/tool interface
(`backend/llm.py`), so the loop is identical on OpenAI, Claude and Ollama.

### Input data

Any CSV / `.xlsx` / `.xls` with a date-like column and a revenue-like column.
Names are matched by whole word (`Order Date`, `created_at`, `GrossRevenue`,
`total_sales`, …); otherwise the first parseable date column and the
highest-variance numeric column are used, and the UI lets you override. Currency
symbols and thousands separators are stripped. At least 10 valid rows are
required for forecasting; a what-if driver column must be numeric on ≥ 80% of rows.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                 # full suite (~90 s, fits several Prophet models)
pytest -m "not slow"   # fast unit tests only
```

CI (`.github/workflows/ci.yml`) runs the Python suite, builds and smoke-tests
both Docker images, lints and builds the web app, and checks the Vercel bundle size.

## Project layout

```
api/index.py              Vercel serverless entry (re-exports the FastAPI app)
vercel.json, .vercelignore
vendor/                   matplotlib stub wheel (bundle size)
backend/
  config.py               settings from .env
  io_utils.py             upload parsing, inspection, file_url download
  observability.py        logging, metrics, rate limiting, Sentry
  main.py                 FastAPI app
  orchestrator.py         pipeline runner
  llm.py                  provider abstraction (OpenAI / Anthropic / Ollama)
  agents/
    data_agent.py
    forecast_agent.py     Prophet + backtest + what-if
    anomaly_agent.py      residual z-scores, monthly shocks
    strategist_tools.py   data-query tools for the strategist
    recommendation_agent.py   strategist (tool loop + static fallback)
    critic_agent.py       fact-checking pass
web/                      Next.js app (see web/README.md)
tests/
Dockerfile, docker-compose.yml, run.ps1
.github/workflows/ci.yml
```
