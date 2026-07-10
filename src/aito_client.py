"""Thin Aito REST client.

Slim version of the framework's `aito_client.py` — covers the surface
most demos actually use:

  - check_connectivity()  — for /api/health
  - get_schema()          — for /api/schema and the AitoPanel "verify yourself" link
  - predict()             — categorical prediction with $why explanations
  - match()               — similarity search
  - search()              — full-text + filter

For richer patterns (relate, batch predict, per-tenant routing, two-layer
disk cache, semaphores for concurrency control, public-demo cold-start
tracking), lift from `aito-accounting-demo/src/aito_client.py`.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any

import httpx

from src.config import Config

# Per-request call log. The FastAPI middleware sets this to an empty list at
# the start of each request and reads it at the end — lets a single response
# expose the sum of *all* Aito calls made for that request (e.g. the predict
# route fans out into predict / predict / search and we want X-Aito-Ms to
# show the total, not just the last leg).
_request_calls: contextvars.ContextVar[list["AitoCall"] | None] = contextvars.ContextVar(
    "_aito_request_calls", default=None
)


class AitoError(Exception):
    """All errors from this client subclass AitoError.

    Routes that want to surface them as HTTP errors should catch this and
    return an error envelope — e.g.:

        try:
            r = client.predict(...)
        except AitoError as e:
            raise HTTPException(status_code=502, detail=str(e))
    """

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class AitoCall:
    """Lightweight record of a single Aito call. Useful for the
    AitoPanel's latency display and for logging.
    """
    op: str       # "_predict" / "_match" / "_search" / "schema"
    ms: float
    status: int


class AitoClient:
    """Synchronous Aito client. One instance per process; thread-safe via httpx."""

    def __init__(self, config: Config) -> None:
        self._url = config.aito_url
        self._headers = {
            "x-api-key": config.aito_key,
            "content-type": "application/json",
        }
        # httpx.Client is thread-safe + pools connections; one for the
        # lifetime of the process beats per-call construction.
        self._http = httpx.Client(
            base_url=self._url,
            headers=self._headers,
            timeout=10.0,
        )
        self.last_call: AitoCall | None = None

    @property
    def base_url(self) -> str:
        return self._url

    def close(self) -> None:
        self._http.close()

    # ── Per-request call tracking ──────────────────────────────────────

    @staticmethod
    def begin_request_log() -> list["AitoCall"]:
        """Start a fresh per-request log. Returns the list the middleware
        will read at end-of-request to build the X-Aito-* headers.
        """
        calls: list[AitoCall] = []
        _request_calls.set(calls)
        return calls

    # ── Low-level ──────────────────────────────────────────────────────

    def _request(self, method: str, path: str, body: dict | None = None, op: str | None = None) -> dict:
        try:
            r = self._http.request(method, path, json=body)
        except httpx.HTTPError as e:
            raise AitoError(f"Aito {path} unreachable: {e}") from e
        # r.elapsed is only valid after the response is read/closed (and
        # not at all under booktest's snapshot-replay mock). Trigger a
        # read and fall back to 0.0 on the replay path.
        try:
            r.read()
            ms = r.elapsed.total_seconds() * 1000
        except (httpx.ResponseNotRead, RuntimeError, AttributeError):
            ms = 0.0
        call = AitoCall(op=op or path, ms=ms, status=r.status_code)
        self.last_call = call
        bucket = _request_calls.get()
        if bucket is not None:
            bucket.append(call)
        if r.status_code >= 400:
            try:
                body_json = r.json()
            except Exception:
                body_json = None
            raise AitoError(
                f"Aito {path} returned {r.status_code}",
                status_code=r.status_code,
                body=body_json,
            )
        return r.json()

    # ── Convenience methods ────────────────────────────────────────────

    def check_connectivity(self) -> bool:
        """True iff /schema returns 2xx. Used by /api/health."""
        try:
            self.get_schema()
            return True
        except AitoError:
            return False

    def get_schema(self) -> dict:
        """Whole-DB schema. Cheap; safe to call on every request."""
        return self._request("GET", "/api/v1/schema", op="schema")

    def predict(
        self,
        table: str,
        where: dict,
        predict_field: str,
        limit: int = 5,
        select: list[Any] | None = None,
    ) -> dict:
        """Categorical prediction with optional $why explanations.

        Pass `select=["feature", "$p", "$why"]` (or similar) to surface
        per-hit explanation factors. Aito only returns $why when asked.
        """
        body: dict[str, Any] = {
            "from": table,
            "where": where,
            "predict": predict_field,
            "limit": limit,
        }
        if select is not None:
            body["select"] = select
        return self._request("POST", "/api/v1/_predict", body, op="_predict")

    def match(
        self,
        table: str,
        where: dict,
        match_field: str,
        limit: int = 5,
    ) -> dict:
        """Find rows similar to the given where-fields. Returns $score per hit."""
        return self._request(
            "POST",
            "/api/v1/_match",
            {"from": table, "where": where, "match": match_field, "limit": limit},
            op="_match",
        )

    def relate(
        self,
        table: str,
        where: dict,
        relate_field: str,
        limit: int = 30,
    ) -> dict:
        """Run a _relate query — discover which values of `relate_field`
        are statistically associated with rows matching `where`.

        Each hit carries lift, frequency counts, probabilities and a
        mutual-information block. Useful for "what features distinguish
        viral posts from flops" style questions.
        """
        return self._request(
            "POST",
            "/api/v1/_relate",
            {"from": table, "where": where, "relate": relate_field, "limit": limit},
            op="_relate",
        )

    def search(
        self,
        table: str,
        where: dict,
        limit: int = 10,
        order_by: str | dict | None = None,
    ) -> dict:
        """Full-text + filter search. orderBy: '$similarity', a field name, or {field, desc}."""
        body: dict = {"from": table, "where": where, "limit": limit}
        if order_by is not None:
            body["orderBy"] = order_by
        return self._request("POST", "/api/v1/_search", body, op="_search")
