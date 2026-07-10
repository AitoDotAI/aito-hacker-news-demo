# Aito query cheatsheet

Reference for the query patterns this demo (and all aito-demo-server demos) reach for. Adapt the request bodies to your schema; the response shapes are stable across Aito instances.

Aito base URL: `${AITO_API_URL}` (e.g. `https://shared.aito.ai/db/your-db`).
Auth header: `x-api-key: ${AITO_API_KEY}`.

All endpoints are `POST` with `Content-Type: application/json` and return JSON.

---

## Predict — categorical (the workhorse)

Predict the value of one field given known values of others. Returns a ranked list with probabilities.

**Endpoint:** `POST /api/v1/_predict`

```json
{
  "from": "submissions",
  "where": {
    "title": "Show HN: I built a thing",
    "domain": "github.com",
    "hour_utc": 14,
    "day_of_week": 1
  },
  "predict": "success_bucket",
  "limit": 5
}
```

**Response:**
```json
{
  "hits": [
    {"feature": "mid",   "$p": 0.41, "$why": [...]},
    {"feature": "low",   "$p": 0.28, ...},
    {"feature": "hit",   "$p": 0.19, ...},
    {"feature": "flop",  "$p": 0.08, ...},
    {"feature": "viral", "$p": 0.04, ...}
  ]
}
```

**Tips:**
- Predict categorical, not continuous. Bucket numeric targets first.
- `$p` is calibrated probability — sum across the prediction space ≈ 1.
- `$why` is the explanation (top contributing fields). Useful for UI tooltips.
- `where` accepts text fields with full sentences — Aito tokenizes and matches.

---

## Predict — binary (headline number)

Same as above, but with two possible values. Use when the answer is "X or not X" and you want a single percentage in the UI.

```json
{
  "from": "submissions",
  "where": { "title": "...", "domain": "..." },
  "predict": "front_page",
  "limit": 2
}
```

Then in the UI: `pct = hits.find(h => h.feature === true).$p * 100`.

---

## Match — similar items by content

Find items most similar to the given fields. Used for "similar past examples" UIs.

**Endpoint:** `POST /api/v1/_match`

```json
{
  "from": "submissions",
  "where": { "title": "Show HN: my project" },
  "match": "title",
  "limit": 5
}
```

`$score` is the similarity score (higher = closer). Use `_match` when you want "what's like this", `_search` when you want "what mentions this".

---

## Search — full-text + filters

Lucene-style query with optional filters. Use for browseable lists.

**Endpoint:** `POST /api/v1/_search`

```json
{
  "from": "submissions",
  "where": { "title": "rust async", "year": 2024 },
  "orderBy": "$similarity",
  "limit": 20
}
```

`orderBy` options: `$similarity` (relevance), any field name (ascending), or `{"field": "score", "desc": true}`.

---

## Schema — what tables/fields exist

Cheap, useful for readiness checks and dynamic UIs.

**Endpoint:** `GET /api/v1/schema`

```json
{
  "schema": {
    "submissions": {
      "type": "table",
      "columns": {
        "title":         { "type": "Text", "analyzer": "english" },
        "score":         { "type": "Int" },
        "success_bucket":{ "type": "String" }
      }
    }
  }
}
```

---

## Multi-tenant routing (if your demo has it)

If the demo serves multiple Aito DBs (e.g. erp's metsa/aurora/studio), the convention is:
- Frontend sets `X-Tenant: <tenant-id>` header on every `/api/*` call
- Backend reads it, picks the right `AitoClient` from a dict keyed by tenant
- Cache keys are scoped: `tenant:<id>:key` so switching tenants doesn't serve stale data

See `aito-erp-demo/src/app.py` for the canonical implementation. Don't roll your own multi-tenant pattern.

---

## Common where-clause patterns

| Goal | Where clause |
|---|---|
| Exact match string | `{ "field": "value" }` |
| Match text (tokenized) | `{ "title": "natural sentence here" }` |
| Range | `{ "year": { "$gte": 2020, "$lt": 2025 } }` |
| Categorical filter | `{ "category": { "$or": ["a", "b"] } }` |
| Negation | `{ "status": { "$not": "deleted" } }` |
| Multiple values must match | `{ "$and": [{...}, {...}] }` |

---

## Performance

- Predict on ~200k-row tables: typical latency 30-100ms (warm).
- Aito instances cold-start in ~1-2s after idle. Use `/health` pings (4-min cron from an external uptime service) to keep warm.
- Cache cheap derivatives in your FastAPI process (in-memory dict, TTL 60s) — see existing demos' `src/cache.py` for the pattern. Don't put per-user data in there; it's a global.

---

## When to NOT use Aito

- Transactional writes where you need ACID — use a real OLTP DB; mirror the relevant slice to Aito for prediction.
- Sub-millisecond latency requirements — Aito is HTTP, network-bound.
- Massive batch predictions (10k+ rows in one request) — chunk into smaller `_predict` calls, parallel-fetch.

---

## Loading data

```bash
# pseudo-CLI; check current aito-cli for exact syntax
aito create-table mytable ./schema.json
aito upload-batch mytable ./data.ndjson --batch-size 10000
```

For batch-load patterns see `aito-cli-tools` repo. Most demos have a `scripts/load-data.py` that handles their specific corpus.
