"""MCP server for the Predictive HN demo.

Exposes the same predict / discover tools as the FastAPI app, but over
the Model Context Protocol so Claude Desktop (or any MCP client) can
call them as tools.

Run standalone:
    uv run python -m src.mcp_server

Claude Desktop config (`~/.config/Claude/claude_desktop_config.json` on
Linux, or the macOS equivalent — see Anthropic's MCP quickstart):

    {
      "mcpServers": {
        "predictive-hn": {
          "command": "uv",
          "args": [
            "--directory",
            "/absolute/path/to/aito-hacker-news-demo",
            "run",
            "python", "-m", "src.mcp_server"
          ]
        }
      }
    }

Requirements:
  - the local Aito Docker container running (port 8200 by default)
  - the hn_submissions table loaded (see scripts/load_aito.py)
  - .env with AITO_API_URL + AITO_API_KEY

The server uses stdio transport (the default) — Claude Desktop will
launch it as a subprocess and talk JSON-RPC over stdin/stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from src.aito_client import AitoClient, AitoError
from src.config import load_config
from src.features_service import category_features
from src.predict_service import PredictRequest, predict_hn

# One persistent AitoClient per process — same pattern as the FastAPI app.
# Errors at import time surface in Claude Desktop's MCP log so config
# problems are visible there instead of silently breaking tool calls.
_config = load_config()
_aito = AitoClient(_config)

mcp = FastMCP("predictive-hn")


# ── Tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def predict_hn_title(
    title: Annotated[str, Field(description="Draft HN submission title to score")],
    domain: Annotated[
        Optional[str],
        Field(default=None, description="Optional URL domain, e.g. 'github.com'"),
    ] = None,
    hour_utc: Annotated[
        Optional[int],
        Field(default=None, ge=0, le=23, description="Posting hour in UTC (0-23)"),
    ] = None,
    day_of_week: Annotated[
        Optional[int],
        Field(default=None, ge=0, le=6, description="Day of week (0=Mon..6=Sun)"),
    ] = None,
    title_length: Annotated[
        Optional[int],
        Field(
            default=None,
            ge=1,
            le=500,
            description=(
                "Override the inferred title length (character count). Use this "
                "to ask 'what if my title were N chars?' without changing the text."
            ),
        ),
    ] = None,
    similar_limit: Annotated[
        Optional[int],
        Field(
            default=None,
            ge=1,
            le=30,
            description="How many similar past submissions to return (default 8).",
        ),
    ] = None,
) -> dict[str, Any]:
    """Predict how a Hacker News submission will perform using Aito's
    inference database against a corpus of ~9,500 recent HN stories.

    Returns:
      - headline: { front_page_pct, label }      — probability of hitting front page (≥50 pts)
      - bucket_distribution: 5-class distribution over flop/low/mid/hit/viral
      - estimated_score: { expected, most_likely_bucket, most_likely_midpoint }
                        expected = Σ p · midpoint (long-tail aware)
                        most_likely_midpoint = the "everyday guess" upvote count
      - estimated_comments: float
      - similar_posts: top 8 prior submissions sharing title tokens, with their actual scores
      - why_top_factors: top 8 contributing features from Aito's $why explanation
    """
    try:
        req = PredictRequest(
            title=title,
            domain=domain,
            hour_utc=hour_utc,
            day_of_week=day_of_week,
            title_length=title_length,
            similar_limit=similar_limit,
        )
        res = predict_hn(_aito, req)
        return json.loads(res.model_dump_json())
    except AitoError as e:
        return {"error": f"Aito error: {e}", "status_code": e.status_code}


@mcp.tool()
def discover_category_features(
    bucket: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Filter to a single bucket (one of: flop, low, mid, hit, viral). "
                "Omit to return features for all five buckets."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Discover which title tokens / domains / posting hours / posting days
    are statistically associated with each success bucket, using Aito's
    _relate endpoint.

    Each feature comes with:
      - lift: how much more likely it is in this bucket vs. the corpus average
      - count_in_bucket / count_total: raw frequencies
      - p_in_bucket / p_overall: probabilities

    Cached in-process after the first call (~20 _relate calls upstream).
    """
    try:
        res = category_features(_aito)
        data = json.loads(res.model_dump_json())
        if bucket:
            buckets = [b for b in data["buckets"] if b["bucket"] == bucket]
            if not buckets:
                return {
                    "error": f"unknown bucket {bucket!r}",
                    "valid": ["flop", "low", "mid", "hit", "viral"],
                }
            data["buckets"] = buckets
        return data
    except AitoError as e:
        return {"error": f"Aito error: {e}", "status_code": e.status_code}


@mcp.tool()
def find_similar_hn_posts(
    title: Annotated[str, Field(description="Title to find similar past posts for")],
    limit: Annotated[
        int,
        Field(default=8, ge=1, le=30, description="Maximum number of posts to return"),
    ] = 8,
) -> dict[str, Any]:
    """Find past HN submissions with overlapping title tokens — same words,
    different outcomes. A handy slice if you don't need the full prediction,
    just want to know "has anything like this been posted before, and what
    happened to it?"
    """
    try:
        # Reuse the prediction pipeline but only surface similar_posts.
        req = PredictRequest(title=title)
        res = predict_hn(_aito, req)
        data = json.loads(res.model_dump_json())
        return {
            "query_title": title,
            "similar_posts": data["similar_posts"][:limit],
        }
    except AitoError as e:
        return {"error": f"Aito error: {e}", "status_code": e.status_code}


# ── Resources ─────────────────────────────────────────────────────────

@mcp.resource("predictive-hn://schema")
def schema_resource() -> str:
    """The hn_submissions table schema — what fields exist and their types.
    Useful as context when Claude wants to know what it can ask about."""
    try:
        schema = _aito.get_schema()
        tables = (schema.get("schema") or {})
        ours = tables.get("hn_submissions")
        if ours is None:
            return f"# Predictive HN schema\n\nhn_submissions table not loaded yet.\n\nTables found: {list(tables.keys())}"
        cols = ours.get("columns") or {}
        lines = [
            "# Predictive HN — hn_submissions schema",
            "",
            f"Aito DB: {_aito.base_url}",
            f"Table:   hn_submissions ({len(cols)} columns)",
            "",
            "| field | type | analyzer / notes |",
            "|---|---|---|",
        ]
        for name, meta in sorted(cols.items()):
            t = meta.get("type", "?")
            extra = []
            if meta.get("analyzer"):
                extra.append(f"analyzer={meta['analyzer']}")
            if meta.get("nullable"):
                extra.append("nullable")
            lines.append(f"| `{name}` | {t} | {', '.join(extra) or '—'} |")
        lines += [
            "",
            "Success buckets: flop (<10), low (10–49), mid (50–149), hit (150–499), viral (500+).",
            "day_of_week: 0=Mon..6=Sun.  hour_utc: 0–23.",
        ]
        return "\n".join(lines)
    except AitoError as e:
        return f"# Predictive HN schema\n\nError: {e}"


# ── Entrypoint ────────────────────────────────────────────────────────

def main() -> None:
    # FastMCP.run() defaults to stdio transport, which is what Claude
    # Desktop expects when it spawns the subprocess.
    mcp.run()


if __name__ == "__main__":
    main()
