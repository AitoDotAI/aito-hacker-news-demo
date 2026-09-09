"""Create the hn_submissions table on a target Aito instance and upload
rows from an NDJSON file.

Usage:
    # Uses AITO_API_URL + AITO_API_KEY from .env (same as the FastAPI app)
    uv run python -m scripts.load_aito \\
        --schema scripts/schema.json \\
        --data data/submissions.ndjson \\
        --table hn_submissions

    # Wipe the table first (handy during iteration)
    uv run python -m scripts.load_aito ... --recreate

Aito batch-upload endpoint accepts JSON arrays. We chunk the file so we
don't blow up memory and so failures are recoverable (we print the last
successful batch index).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src.config import load_config

load_dotenv()

DEFAULT_BATCH_SIZE = 1000


def _client(base_url: str, api_key: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        headers={"x-api-key": api_key, "content-type": "application/json"},
        timeout=60.0,
    )


def table_exists(client: httpx.Client, table: str) -> bool:
    r = client.get(f"/api/v1/schema/{table}")
    return r.status_code == 200


def drop_table(client: httpx.Client, table: str) -> None:
    r = client.delete(f"/api/v1/schema/{table}")
    if r.status_code not in (200, 204, 404):
        raise RuntimeError(f"DELETE schema/{table} → {r.status_code}: {r.text[:300]}")


def create_table(client: httpx.Client, table: str, schema_path: Path) -> None:
    raw = json.loads(schema_path.read_text())
    table_schema = raw["schema"][table]
    r = client.put(f"/api/v1/schema/{table}", json=table_schema)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"PUT schema/{table} → {r.status_code}: {r.text[:500]}")
    print(f"  created table {table}")


def upload_batch(client: httpx.Client, table: str, rows: list[dict]) -> None:
    r = client.post(f"/api/v1/data/{table}/batch", json=rows)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"POST data/{table}/batch (size={len(rows)}) → {r.status_code}: {r.text[:500]}"
        )


def iter_batches(ndjson_path: Path, batch_size: int):
    batch: list[dict] = []
    with ndjson_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            batch.append(json.loads(line))
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--schema", required=True, help="path to schema.json")
    ap.add_argument("--data", required=True, help="path to NDJSON data file")
    ap.add_argument("--table", default="hn_submissions")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument(
        "--recreate",
        action="store_true",
        help="drop the table first if it exists (loses existing data)",
    )
    ap.add_argument(
        "--skip-create",
        action="store_true",
        help="assume the table already exists; just upload data",
    )
    ap.add_argument(
        "--allow-master",
        action="store_true",
        help=(
            "permit destructive writes against the master env. Without this, "
            "--recreate refuses to run unless AITO_ENV names a branch."
        ),
    )
    args = ap.parse_args()

    schema_path = Path(args.schema)
    data_path = Path(args.data)
    if not schema_path.exists():
        ap.error(f"schema not found: {schema_path}")
    if not data_path.exists():
        ap.error(f"data not found: {data_path}")

    cfg = load_config()

    # Production serves master. Dropping a table there takes the live demo
    # down, so make it an explicit choice rather than a default.
    on_master = cfg.aito_env is None
    if on_master and args.recreate and not args.allow_master:
        ap.error(
            "refusing to --recreate on the master env, which production "
            "serves. Set AITO_ENV=<branch> to target a branch (create one "
            "with POST /api/v2/_envs), or pass --allow-master if you really "
            "mean to rebuild production's table."
        )

    print(f"Target Aito: {cfg.api_base}")
    print(f"Env:         {cfg.aito_env or 'master (production)'}")
    print(f"Source:      {data_path} ({data_path.stat().st_size / 1e6:.1f} MB)")

    with _client(cfg.api_base, cfg.aito_key) as client:
        if not args.skip_create:
            if table_exists(client, args.table):
                if args.recreate:
                    print(f"  table {args.table} exists; dropping (--recreate)")
                    drop_table(client, args.table)
                    create_table(client, args.table, schema_path)
                else:
                    print(
                        f"  table {args.table} already exists. Pass --recreate to drop, "
                        f"or --skip-create to append."
                    )
            else:
                create_table(client, args.table, schema_path)

        total = 0
        t0 = time.time()
        for i, batch in enumerate(iter_batches(data_path, args.batch_size)):
            upload_batch(client, args.table, batch)
            total += len(batch)
            elapsed = time.time() - t0
            rate = total / max(elapsed, 0.001)
            print(
                f"  batch {i + 1}: +{len(batch)}  total={total:>7}  "
                f"({rate:.0f} rows/s, elapsed={elapsed:.0f}s)",
                flush=True,
            )

    elapsed = time.time() - t0
    print(f"\nDone. Uploaded {total} rows in {elapsed:.0f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
