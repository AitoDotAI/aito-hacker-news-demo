"""Smoke-test the configured Aito DB by fetching its schema.

booktest captures the httpx interactions on first run and replays them
on subsequent runs — so Aito-dependent tests stay fast and deterministic.

When the Aito schema legitimately changes (you load a new table, add a
column), regenerate the snapshot with:

    ./do test-book --update-snapshots

Run normally with:

    ./do test-book
"""

import booktest as bt
import httpx

from src.config import load_config


@bt.snapshot_httpx()
def test_aito_schema(t: bt.TestCaseRun):
    """Fetch the schema and book the table list."""
    config = load_config()

    t.h1("Aito schema")
    t.tln(f"DB: `{config.aito_url}`")
    t.tln("")

    with httpx.Client(
        base_url=config.aito_url,
        headers={"x-api-key": config.aito_key, "content-type": "application/json"},
        timeout=10.0,
    ) as client:
        r = client.get("/api/v1/schema")
        r.raise_for_status()
        data = r.json()

    tables = sorted((data.get("schema") or {}).keys())

    t.h2("Tables")
    if not tables:
        t.tln("_(empty schema — load data first)_")
    else:
        for table in tables:
            cols = (data["schema"][table].get("columns") or {})
            t.iln(f"- `{table}` — {len(cols)} columns")

    t.tln("")
    t.assertln("schema returns successfully", isinstance(data, dict))
