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

If the backend fails to import (missing dependency, platform quirk), the
function still starts and every request returns a JSON diagnosis with the
traceback — much easier to act on than Vercel's generic
FUNCTION_INVOCATION_FAILED page.

Everything else — CORS, the 25 MB cap, optional X-API-Key auth, lazy LLM
provider check, RecommendationError → recommendations_error — lives in
backend/main.py and the agents, unchanged from the container deployment.
"""

import json
import os
import platform
import sys
import traceback
from urllib.parse import unquote

_PREFIX = "/api/index"

_import_error: dict | None = None
try:
    from backend.main import app as fastapi_app
except Exception as exc:  # noqa: BLE001 — we want to report anything
    _import_error = {
        "error": "backend failed to import",
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc().splitlines()[-25:],
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "sys_path_head": sys.path[:5],
        "hint": (
            "Check the build log for the failing package. Common causes: PIP_COMPILE not set "
            "(bundle over 250 MB), a wheel without a manylinux build for this Python version, "
            "or a missing environment variable."
        ),
    }
    fastapi_app = None


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


async def _send_json(send, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):  # ASGI callable Vercel looks for
    if scope.get("type") == "lifespan":
        # Nothing to start up; acknowledge so the runtime doesn't wait
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if fastapi_app is None:
        await _send_json(send, 500, _import_error)
        return

    try:
        await fastapi_app(_rewrite_path(scope), receive, send)
    except Exception as exc:  # noqa: BLE001 — surface request-time crashes too
        await _send_json(send, 500, {
            "error": "unhandled exception in backend",
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc().splitlines()[-25:],
        })
