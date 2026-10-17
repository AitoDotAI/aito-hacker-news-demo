"""FastAPI app for the Predictive Hacker News demo.

Routes:
  - GET  /health           — cheap liveness, no Aito call
  - GET  /api/health       — readiness, includes Aito connectivity
  - GET  /api/schema       — pass-through to Aito's /schema (AitoPanel "verify live" link)
  - POST /api/predict-hn   — predict performance for a given HN title

The static mount must stay last so it doesn't shadow /api/*.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from src.aito_client import AitoClient, AitoError
from src.config import load_config
from src.features_service import CategoryFeaturesResponse, category_features
from src.predict_service import PredictRequest, PredictResponse, predict_hn

config = load_config()
aito = AitoClient(config)

@asynccontextmanager
async def lifespan(_: FastAPI):
    # _prewarm is defined further down; it runs after import completes.
    threading.Thread(target=_prewarm, name="aito-prewarm", daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Predictive Hacker News",
    description="Predict the performance of a Hacker News submission, powered by Aito.",
    version="0.1.0",
)


# ── Middleware: surface Aito latency in response headers ─────────────
#
# The LatencyBadge in the frontend reads X-Aito-Ms / X-Aito-Calls /
# X-Aito-Ops from every /api/* response. We sum across *all* Aito calls
# made during the request — the predict route fans out into several
# (predict bucket, predict front_page, similar search) and we want the
# header to reflect the actual cost the user sees.

@app.middleware("http")
async def aito_latency_headers(request: Request, call_next):
    calls = AitoClient.begin_request_log()
    response: Response = await call_next(request)
    if calls:
        total_ms = sum(c.ms for c in calls)
        response.headers["X-Aito-Ms"] = f"{total_ms:.1f}"
        response.headers["X-Aito-Calls"] = str(len(calls))
        response.headers["X-Aito-Ops"] = ",".join(f"{c.op}:{c.ms:.1f}" for c in calls)
    return response


# ── Health ────────────────────────────────────────────────────────

@app.get("/health")
def liveness():
    return {"ok": True}


@app.get("/api/health")
def readiness():
    connected = aito.check_connectivity()
    return {
        "status": "ok" if connected else "degraded",
        "aito_url": aito.base_url,
        "aito_connected": connected,
    }


@app.get("/api/schema")
def schema():
    try:
        return aito.get_schema()
    except AitoError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Predict ───────────────────────────────────────────────────────

#
# Responses are cached on the exact request. The corpus is static between
# reloads, so an identical request always gets an identical answer, and
# launch traffic is dominated by repeats (the example titles, the title
# people saw in the post). X-Cache tells the client whether Aito ran, so
# a cached answer never passes for a fresh query's latency.

_PREDICT_CACHE_MAX = 4096
_predict_cache: OrderedDict[str, PredictResponse] = OrderedDict()
_predict_cache_lock = threading.Lock()


@app.post("/api/predict-hn", response_model=PredictResponse)
def predict(req: PredictRequest, response: Response):
    key = req.model_dump_json()
    with _predict_cache_lock:
        hit = _predict_cache.get(key)
        if hit is not None:
            _predict_cache.move_to_end(key)
    if hit is not None:
        response.headers["X-Cache"] = "hit"
        return hit
    try:
        result = predict_hn(aito, req)
    except AitoError as e:
        raise HTTPException(status_code=502, detail=str(e))
    with _predict_cache_lock:
        _predict_cache[key] = result
        if len(_predict_cache) > _PREDICT_CACHE_MAX:
            _predict_cache.popitem(last=False)
    response.headers["X-Cache"] = "miss"
    return result


# The first query against a cold Aito index takes ~1.7 s against ~60 ms
# warm (measured 2026-10-10). Warm it in the background at startup so the
# first visitor after a deploy doesn't pay for it. Best effort: a failure
# here only means the first real request is slow.
_PREWARM_TITLES = [
    "Show HN: A minimal Postgres client written in Rust",
    "OpenAI announces new model with breakthrough reasoning",
    "I built a todo app over the weekend",
]


def _prewarm() -> None:
    for title in _PREWARM_TITLES:
        try:
            predict_hn(aito, PredictRequest(title=title))
        except Exception as e:  # noqa: BLE001 — never let warmup kill the app
            print(f"prewarm failed for {title!r}: {e}")





@app.get("/api/category-features", response_model=CategoryFeaturesResponse)
def features(refresh: bool = False):
    """Top features (title tokens / domains / hours / days) associated
    with each success_bucket, via Aito's _relate. First call fans out
    into ~20 Aito calls; subsequent calls are cache hits.

    Pass ?refresh=true to force a recompute (e.g. after reloading the
    corpus).
    """
    try:
        return category_features(aito, force=refresh)
    except AitoError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Static files — keep this last ─────────────────────────────────

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "out"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
