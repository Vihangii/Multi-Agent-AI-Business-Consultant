"""
Vercel serverless entry point.

Vercel's Python runtime runs any ASGI app exported as `app` from a file under
api/. vercel.json rewrites every path to this one function, so the whole
FastAPI application — /health, /inspect, /analyze, /docs — is served from a
single bundle. (One function, not one per route: each Python function on
Vercel carries its own copy of the ~200 MB pandas/Prophet dependency set.)

The runtime passes the *rewritten* path (`/api/index...`) rather than the
original one, so the wrapper below strips that prefix before FastAPI routes
the request. `/api/index/health` and `/health` both work; the original
path is also honoured when Vercel provides it in `x-vercel-original-path`.

Everything else — CORS, the 25 MB cap, optional X-API-Key auth, lazy LLM
provider check, RecommendationError → recommendations_error — lives in
backend/main.py and the agents, unchanged from the container deployment.
"""

from urllib.parse import unquote

from backend.main import app as fastapi_app

_PREFIX = "/api/index"


def _rewrite_path(scope: dict) -> dict:
    if scope.get("type") != "http":
        return scope
    path = scope.get("path") or "/"

    # Prefer the original path if the platform forwards it
    original = None
    for name, value in scope.get("headers") or []:
        if name == b"x-vercel-original-path":
            original = unquote(value.decode("latin-1")).split("?", 1)[0]
            break

    if original:
        new_path = original or "/"
    elif path == _PREFIX or path.startswith(_PREFIX + "/"):
        new_path = path[len(_PREFIX):] or "/"
    else:
        return scope

    scope = dict(scope)
    scope["path"] = new_path
    scope["raw_path"] = new_path.encode("utf-8")
    return scope


async def app(scope, receive, send):  # ASGI callable Vercel looks for
    await fastapi_app(_rewrite_path(scope), receive, send)
