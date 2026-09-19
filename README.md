# Multi-Agent AI Business Consultant

Upload a sales/revenue spreadsheet and get back a cleaned dataset, a Prophet
revenue forecast, and a GPT-written strategic report — through a FastAPI backend
and a Streamlit dashboard.

```
CSV / Excel ──▶ Data Agent ──▶ Forecast Agent ──▶ Recommendation Agent ──▶ Dashboard
                (pandas)        (Prophet)          (OpenAI)                (Streamlit)
```

| Stage | Module | What it does |
|---|---|---|
| 1. Data Agent | `backend/agents/data_agent.py` | Detects the date and revenue columns, parses currency strings, aggregates duplicate dates, computes growth / monthly / volatility stats |
| 2. Forecast Agent | `backend/agents/forecast_agent.py` | Auto-detects daily / weekly / monthly granularity, fits Prophet, returns a ~6-month forecast with 95% intervals |
| 3. Recommendation Agent | `backend/agents/recommendation_agent.py` | Sends the stats + forecast to OpenAI and returns a markdown strategy report |
| Orchestrator | `backend/orchestrator.py` | Runs the three stages and packages the result |
| API | `backend/main.py` | `GET /`, `GET /health`, `POST /analyze` |
| UI | `frontend/app.py` | Streamlit dashboard: KPIs, Plotly forecast chart, AI report, data tables |

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
| `BACKEND_URL` | `http://localhost:8000` | Where the Streamlit app finds the API |

## Run

Open two terminals (with the venv activated in each):

```bash
# 1. Backend
uvicorn backend.main:app --reload --port 8000

# 2. Frontend
streamlit run frontend/app.py
```

Then open http://localhost:8501, download the sample CSV from the sidebar (or
upload your own), and click **Run Consultant Pipeline**.
Interactive API docs are at http://localhost:8000/docs.

### Input data

Any CSV / `.xlsx` / `.xls` with at least one date-like column and one revenue-like
column. Column names are matched by whole word (`Order Date`, `created_at`,
`GrossRevenue`, `total_sales`, …); if nothing matches, the first parseable
date column and the highest-variance numeric column are used. Currency
symbols and thousands separators are stripped automatically. At least 10
valid rows are required for forecasting.

### API

```bash
curl -F "file=@sales.csv" "http://localhost:8000/analyze?periods=90&frequency=D&skip_recommendations=true"
```

Query parameters:

- `periods` — forecast horizon (2–1000). Default ≈ 6 months for the detected frequency.
- `frequency` — `D`, `W` or `MS`. Auto-detected if omitted.
- `skip_recommendations` — `true` to skip the OpenAI stage.

The response contains `analysis`, `forecast_summary`, `forecast`, `cleaned_data`,
and either `recommendations` (markdown) or `recommendations_error` if stage 3
could not run. Stage 3 failing never fails the request; stages 1–2 results are
always returned.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                 # full suite (~20 s, fits a few Prophet models)
pytest -m "not slow"   # fast unit tests only
```

## Project layout

```
backend/
  config.py               settings from .env
  main.py                 FastAPI app
  orchestrator.py         pipeline runner
  agents/
    data_agent.py
    forecast_agent.py
    recommendation_agent.py
frontend/
  app.py                  Streamlit dashboard
tests/
```
