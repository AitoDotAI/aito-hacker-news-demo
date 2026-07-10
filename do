#!/usr/bin/env bash
# Local-dev wrapper for the demo template. Replace name + commands as your
# demo grows; the platform only requires that production `uvicorn src.app:app`
# can be started and that `frontend/out/` exists for static export.
#
#   ./do install                  uv sync + npm install (one-time after bootstrap)
#   ./do dev                      run backend (uvicorn) + frontend (next dev)
#   ./do build                    build the frontend static export (frontend/out/)
#   ./do backend                  run backend only (foreground; matches production shape)
#   ./do test                     run all tests (pytest discovers book/ + tests/)
#   ./do test-book                run booktest snapshot tests only (book/)
#   ./do mcp                      run the MCP server (stdio) for Claude Desktop
#   ./do screenshot-teaser        render assets/teaser.html → assets/teaser.png (1200×630)
#   ./do screenshot-pages [...]   desktop full-page screenshots of given paths
#   ./do inspect-mobile [...]     iPhone-sized screenshots of given paths
#   ./do clean                    wipe build artifacts

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BACKEND_PORT="${BACKEND_PORT:-8401}"
FRONTEND_PORT="${FRONTEND_PORT:-8600}"

die() { echo "✗ $*" >&2; exit 1; }
say() { echo "→ $*"; }

cmd_install() {
  command -v uv >/dev/null 2>&1 || die "uv not found (see https://docs.astral.sh/uv/)"
  command -v npm >/dev/null 2>&1 || die "npm not found"
  say "uv sync"
  uv sync
  say "npm install (frontend)"
  ( cd frontend && npm install --no-audit --no-fund )
}

cmd_build() {
  ( cd frontend && NODE_ENV=production npx next build )
  say "frontend/out/ ready ($(find frontend/out -type f | wc -l) files)"
}

cmd_backend() {
  exec uv run uvicorn src.app:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload
}

cmd_dev() {
  [ -d frontend/node_modules ] || cmd_install
  say "backend → http://localhost:${BACKEND_PORT} (uvicorn, hot-reload)"
  say "frontend → http://localhost:${FRONTEND_PORT} (next dev, proxies /api/* → backend)"
  ( BACKEND_PORT="$BACKEND_PORT" uv run uvicorn src.app:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload ) &
  BACK=$!
  trap 'kill $BACK 2>/dev/null || true' EXIT INT TERM
  ( cd frontend && BACKEND_PORT="$BACKEND_PORT" npx next dev -p "$FRONTEND_PORT" )
}

cmd_test() {
  exec uv run pytest "$@"
}

cmd_test_book() {
  # booktest tests live under book/. First run records httpx interactions
  # into books/; subsequent runs replay. Update snapshots with --update-snapshots.
  exec uv run pytest book/ "$@"
}

cmd_screenshot_teaser() {
  [ -d frontend/node_modules ] || cmd_install
  ( cd frontend && node scripts/screenshot-teaser.cjs )
}

cmd_screenshot_pages() {
  [ -d frontend/node_modules ] || cmd_install
  ( cd frontend && node scripts/screenshot-pages.cjs "$@" )
}

cmd_inspect_mobile() {
  [ -d frontend/node_modules ] || cmd_install
  ( cd frontend && node scripts/inspect-mobile.cjs "$@" )
}

cmd_mcp() {
  # Launch the stdio MCP server. Claude Desktop spawns this as a
  # subprocess via the config snippet in README.md.
  exec uv run python -m src.mcp_server
}

cmd_clean() {
  rm -rf frontend/.next frontend/out .pytest_cache frontend/scripts/output/*
  find . -type d -name __pycache__ -prune -exec rm -rf {} +
  say "cleaned"
}

cmd_help() { sed -n '1,20p' "$0" | sed -n '/^#/p'; }

case "${1:-help}" in
  install)             shift; cmd_install "$@" ;;
  dev)                 shift; cmd_dev "$@" ;;
  build)               shift; cmd_build "$@" ;;
  backend)             shift; cmd_backend "$@" ;;
  test)                shift; cmd_test "$@" ;;
  test-book)           shift; cmd_test_book "$@" ;;
  mcp)                 shift; cmd_mcp "$@" ;;
  screenshot-teaser)   shift; cmd_screenshot_teaser "$@" ;;
  screenshot-pages)    shift; cmd_screenshot_pages "$@" ;;
  inspect-mobile)      shift; cmd_inspect_mobile "$@" ;;
  clean)               shift; cmd_clean "$@" ;;
  help|-h|--help)      cmd_help ;;
  *) die "unknown command: $1 (run './do help')" ;;
esac
