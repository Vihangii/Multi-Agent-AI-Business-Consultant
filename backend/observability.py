"""
Observability: structured request logging, an in-process metrics registry
exposed in Prometheus text format, optional Sentry, and a per-client rate
limiter.

Everything here is dependency-free except Sentry, which is imported only when
SENTRY_DSN is set. Counters and the rate limiter are in-process: on a
multi-instance or serverless deployment each instance keeps its own numbers
(good enough for a dashboard; use a shared store if you need global limits).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from backend.config import LOG_FORMAT, RATE_LIMIT_PER_MINUTE, SENTRY_DSN

logger = logging.getLogger("backend.http")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """One JSON object per line — easy to ship to any log aggregator."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    root.addHandler(handler)
    # cmdstanpy logs every chain start/stop at INFO — noisy in request logs
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


@dataclass
class Metrics:
    """Minimal counter/histogram registry rendered in Prometheus text format."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: float = field(default_factory=time.time)
    requests_total: dict[tuple[str, str, str], int] = field(default_factory=lambda: defaultdict(int))
    duration_sum: dict[tuple[str, str], float] = field(default_factory=lambda: defaultdict(float))
    duration_count: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    duration_buckets: dict[tuple[str, str, float], int] = field(default_factory=lambda: defaultdict(int))
    in_flight: int = 0
    pipeline_runs: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    rate_limited_total: int = 0

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self.lock:
            self.requests_total[(method, route, str(status))] += 1
            self.duration_sum[(method, route)] += seconds
            self.duration_count[(method, route)] += 1
            for b in _BUCKETS:
                if seconds <= b:
                    self.duration_buckets[(method, route, b)] += 1

    def record_pipeline(self, outcome: str) -> None:
        with self.lock:
            self.pipeline_runs[outcome] += 1

    def render(self) -> str:
        with self.lock:
            lines = [
                "# HELP http_requests_total Total HTTP requests.",
                "# TYPE http_requests_total counter",
            ]
            for (m, r, s), v in sorted(self.requests_total.items()):
                lines.append(f'http_requests_total{{method="{m}",route="{r}",status="{s}"}} {v}')

            lines += [
                "# HELP http_request_duration_seconds Request latency.",
                "# TYPE http_request_duration_seconds histogram",
            ]
            for (m, r), cnt in sorted(self.duration_count.items()):
                for b in _BUCKETS:
                    lines.append(
                        f'http_request_duration_seconds_bucket{{method="{m}",route="{r}",le="{b}"}} '
                        f"{self.duration_buckets[(m, r, b)]}"
                    )
                lines.append(f'http_request_duration_seconds_bucket{{method="{m}",route="{r}",le="+Inf"}} {cnt}')
                lines.append(f'http_request_duration_seconds_sum{{method="{m}",route="{r}"}} {self.duration_sum[(m, r)]:.6f}')
                lines.append(f'http_request_duration_seconds_count{{method="{m}",route="{r}"}} {cnt}')

            lines += [
                "# HELP http_requests_in_flight Requests currently being handled.",
                "# TYPE http_requests_in_flight gauge",
                f"http_requests_in_flight {self.in_flight}",
                "# HELP pipeline_runs_total Analysis pipeline runs by outcome.",
                "# TYPE pipeline_runs_total counter",
            ]
            for outcome, v in sorted(self.pipeline_runs.items()):
                lines.append(f'pipeline_runs_total{{outcome="{outcome}"}} {v}')
            lines += [
                "# HELP rate_limited_requests_total Requests rejected by the rate limiter.",
                "# TYPE rate_limited_requests_total counter",
                f"rate_limited_requests_total {self.rate_limited_total}",
                "# HELP process_uptime_seconds Seconds since this process started.",
                "# TYPE process_uptime_seconds gauge",
                f"process_uptime_seconds {time.time() - self.started_at:.0f}",
            ]
            return "\n".join(lines) + "\n"


metrics = Metrics()


# ---------------------------------------------------------------------------
# Rate limiting (token bucket per client)
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Allows `per_minute` requests per client per minute with burst capacity of
    the same size. `per_minute <= 0` disables limiting.
    """

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.capacity = float(per_minute)
        self.refill_per_sec = per_minute / 60.0
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_ts)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Returns (allowed, seconds_until_next_token)."""
        if self.per_minute <= 0:
            return True, 0.0
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return True, 0.0
            self._buckets[key] = (tokens, now)
            return False, (1.0 - tokens) / self.refill_per_sec

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)

# Routes that do heavy work and are therefore rate-limited
RATE_LIMITED_PATHS = {"/analyze"}


def client_key(request: Request) -> str:
    """Client identity for rate limiting: API key if present, else IP (behind proxies: X-Forwarded-For)."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key[:12]}"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return f"ip:{fwd.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Request id + timing + access log + metrics + rate limiting."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        path = request.url.path
        start = time.perf_counter()

        if path in RATE_LIMITED_PATHS and request.method == "POST":
            allowed, retry_after = rate_limiter.check(client_key(request))
            if not allowed:
                with metrics.lock:
                    metrics.rate_limited_total += 1
                metrics.observe(request.method, path, 429, time.perf_counter() - start)
                logger.warning(
                    "rate limited",
                    extra={"extra_fields": {"request_id": request_id, "path": path, "client": client_key(request)}},
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Rate limit exceeded ({rate_limiter.per_minute}/min). Try again shortly."},
                    headers={"Retry-After": str(max(1, int(retry_after + 0.999))), "X-Request-ID": request_id},
                )

        with metrics.lock:
            metrics.in_flight += 1
        try:
            response = await call_next(request)
        except Exception:
            metrics.observe(request.method, path, 500, time.perf_counter() - start)
            logger.exception("unhandled error", extra={"extra_fields": {"request_id": request_id, "path": path}})
            raise
        finally:
            with metrics.lock:
                metrics.in_flight -= 1

        elapsed = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", path)
        metrics.observe(request.method, route, response.status_code, elapsed)
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={elapsed * 1000:.0f}"
        logger.info(
            "%s %s -> %d in %.0f ms",
            request.method, path, response.status_code, elapsed * 1000,
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000),
                    "client": client_key(request),
                }
            },
        )
        return response


def metrics_response() -> PlainTextResponse:
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------

def init_sentry() -> bool:
    """Initialise Sentry when SENTRY_DSN is set and sentry-sdk is installed."""
    if not SENTRY_DSN:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry.")
        return False
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    logger.info("Sentry initialised")
    return True
