# Multi-Agent AI Business Consultant

Upload a sales/revenue spreadsheet and get back a cleaned dataset, a Prophet
revenue forecast, and a GPT-written strategic report.

```
CSV / Excel ──▶ Data Agent ──▶ Forecast Agent ──▶ Recommendation Agent ──▶ Dashboard
                (pandas)        (Prophet)          (OpenAI)                (Streamlit)
```

Two frontends share the same backend pipeline:

- **Streamlit** (`frontend/app.py`) — runs the agents **in-process**; one command
  starts the whole app. Best for local use and demos.
- **Next.js** (`web/`) — a React web app **deployable on Vercel** that talks to
  the FastAPI REST API. Best for hosting publicly. See [web/README.md](web/README.md).

| Stage | Module | What it does |
|---|---|---|
| 1. Data Agent | `backend/agents/data_agent.py` | Detects the date and revenue columns, parses currency strings, aggregates duplicate dates, computes growth / monthly / volatility stats |
| 2. Forecast Agent | `backend/agents/forecast_agent.py` | Auto-detects daily / weekly / monthly granularity, fits Prophet, returns a ~6-month forecast with 95% intervals, and backtests itself on the last 20% of history (MAPE / MAE / coverage) |
| 3. Recommendation Agent | `backend/agents/recommendation_agent.py` | Sends the stats + forecast to OpenAI and returns a markdown strategy report |
| Orchestrator | `backend/orchestrator.py` | Runs the three stages and packages the result |
| Upload parsing | `backend/io_utils.py` | Shared CSV/Excel validation + parsing used by both the API and the dashboard |
| API (optional) | `backend/main.py` | `GET /`, `GET /health`, `POST /inspect`, `POST /analyze` |
| Streamlit UI | `frontend/app.py` | Dashboard: column picker, KPIs, Plotly forecast chart, accuracy panel, AI report, data tables. Runs the pipeline in-process or via the API |
| Next.js UI | `web/` | Same features as a React/Tailwind app for Vercel; calls the REST API |

## Requirements

- Python **3.12** (3.13/3.14 don't yet have wheels for the pinned Prophet/NumPy)
- An OpenAI API key — **optional**. Without one, stages 1–2 still run; tick
  *Skip AI Recommendations* in the UI or pass `skip_recommendations=true`.

## Setup

```powershell
# Windows
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # then edit .env and set OPENAI_API_KEY
```

```bash
# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit .env and set OPENAI_API_KEY
```

All settings live in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | – | Enables stage 3. Leave the placeholder to run without it |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model used for recommendations |
| `BACKEND_HOST` / `BACKEND_PORT` | `0.0.0.0` / `8000` | Where uvicorn listens |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `API_KEY` | – | When set, `/analyze` and `/inspect` require an `X-API-Key` header |
| `BACKEND_MODE` | `builtin` | Dashboard engine: `builtin` (in-process) or `remote` (call the API) |
| `BACKEND_URL` | `http://localhost:8000` | Where the dashboard finds the API in `remote` mode |

## Run

### One command

```powershell
.\run.ps1                     # Windows: creates venv + .env if missing, opens the dashboard
```

```bash
streamlit run frontend/app.py  # any OS, with the venv activated
```

Open http://localhost:8501, download the sample CSV from the sidebar (or upload
your own), and click **Run Consultant Pipeline**. Nothing else needs to be
running — the agents execute inside the Streamlit process.

### With Docker

```bash
cp .env.example .env        # set OPENAI_API_KEY if you have one
docker compose up --build   # dashboard on http://localhost:8501
```

### Next.js web app (Vercel)

```bash
uvicorn backend.main:app --reload --port 8000   # terminal 1: the API
cd web && cp .env.example .env.local && npm install && npm run dev   # terminal 2: http://localhost:3000
```

Deploy: import the repo in Vercel with **Root Directory = `web`** and set
`NEXT_PUBLIC_API_URL` to your hosted backend. Full steps in [web/README.md](web/README.md).

### With the REST API as well

Only needed if you want to call the pipeline from other programs, or run the
dashboard and the compute on different machines.

```powershell
.\run.ps1 -WithApi            # Windows: API + dashboard (dashboard in remote mode)
```

```bash
uvicorn backend.main:app --reload --port 8000     # terminal 1
BACKEND_MODE=remote streamlit run frontend/app.py # terminal 2
```

```bash
docker compose --profile api up   # Docker: adds the API on :8000
```

Interactive API docs are at http://localhost:8000/docs.

### Input data

Any CSV / `.xlsx` / `.xls` with at least one date-like column and one revenue-like
column. Column names are matched by whole word (`Order Date`, `created_at`,
`GrossRevenue`, `total_sales`, …); if nothing matches, the first parseable
date column and the highest-variance numeric column are used. The sidebar
shows what was detected and lets you override it. Currency symbols and
thousands separators are stripped automatically. At least 10 valid rows are
required for forecasting.

### API

```bash
# What would be detected? (columns, preview)
curl -F "file=@sales.csv" http://localhost:8000/inspect

# Run the pipeline
curl -F "file=@sales.csv" "http://localhost:8000/analyze?periods=90&frequency=D&skip_recommendations=true"

# With explicit columns and an API key
curl -H "X-API-Key: $API_KEY" -F "file=@sales.csv" \
  "http://localhost:8000/analyze?date_column=OrderDate&revenue_column=Total"
```

`/analyze` query parameters:

- `periods` — forecast horizon (2–1000). Default ≈ 6 months for the detected frequency.
- `frequency` — `D`, `W` or `MS`. Auto-detected if omitted.
- `skip_recommendations` — `true` to skip the OpenAI stage.
- `date_column`, `revenue_column` — override auto-detection.

The response contains `columns`, `analysis`, `forecast_summary` (including an
`accuracy` block with backtest MAPE / MAE / interval coverage when there is
enough history), `forecast`, `cleaned_data`, and either `recommendations`
(markdown) or `recommendations_error` if stage 3 could not run. Stage 3
failing never fails the request; stages 1–2 results are always returned.

Both upload endpoints reject files over `MAX_UPLOAD_MB` (413) and, when
`API_KEY` is set, requests without a matching `X-API-Key` header (401).

## Tests

```bash
pip install -r requirements-dev.txt
pytest                 # full suite (~1 min, fits several Prophet models)
pytest -m "not slow"   # fast unit tests only
```

CI (`.github/workflows/ci.yml`) runs the Python suite, builds and smoke-tests the
Docker image, and lints + builds the Next.js app on every push and PR.

## Project layout

```
backend/
  config.py               settings from .env
  io_utils.py             shared upload parsing
  main.py                 FastAPI app (optional)
  orchestrator.py         pipeline runner
  agents/
    data_agent.py
    forecast_agent.py
    recommendation_agent.py
frontend/
  app.py                  Streamlit dashboard
web/                      Next.js frontend (Vercel)
tests/
Dockerfile, docker-compose.yml
.github/workflows/ci.yml
```
