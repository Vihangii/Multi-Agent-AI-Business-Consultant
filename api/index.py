"""
Vercel serverless entry point.

Vercel's Python runtime runs any ASGI app exported as `app` from a file under
api/. vercel.json rewrites every path to this one function, so the whole
FastAPI application — /health, /inspect, /analyze, /docs — is served from a
single bundle. (One function, not one per route: each Python function on
Vercel carries its own copy of the ~200 MB pandas/Prophet dependency set.)

Everything else — CORS, the 25 MB cap, optional X-API-Key auth, lazy OpenAI
key check, RecommendationError → recommendations_error — lives in
backend/main.py and the agents, unchanged from the container deployment.
"""

from backend.main import app  # noqa: F401  (Vercel looks for `app`)
