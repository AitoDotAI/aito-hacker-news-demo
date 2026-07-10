{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python312;
in
pkgs.mkShell {
  name = "aito-hacker-news-demo";

  buildInputs = [
    # Python (backend: FastAPI + uvicorn via uv)
    python
    pkgs.uv

    # Node / Next.js frontend
    pkgs.nodejs_20
    pkgs.corepack

    # Playwright system dependencies (screenshot scripts in frontend/scripts/)
    pkgs.playwright-driver.browsers

    # Dev tools
    pkgs.jq
    pkgs.curl
    pkgs.httpie
    pkgs.watchexec
  ];

  shellHook = ''
    # Let uv manage the virtualenv against the nix-provided interpreter.
    export UV_PYTHON_PREFERENCE=only-system

    # Sync deps on shell entry (no-op if already in sync).
    if [ -f pyproject.toml ]; then
      uv sync --quiet 2>/dev/null || true
    fi

    # Use nix-managed Playwright browsers rather than `npx playwright install`.
    export PLAYWRIGHT_BROWSERS_PATH="${pkgs.playwright-driver.browsers}"
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

    # Load .env if present (gitignored; holds AITO_API_KEY etc.)
    if [ -f .env ]; then
      set -a
      # shellcheck disable=SC1091
      . ./.env
      set +a
    fi

    # Project env defaults
    export AITO_API_URL="''${AITO_API_URL:-http://localhost:8200}"
    export AITO_API_KEY="''${AITO_API_KEY:-}"
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONUNBUFFERED=1

    # Remind if Aito key is missing
    if [ -z "$AITO_API_KEY" ]; then
      echo ""
      echo "  AITO_API_KEY not set. Export it or add to .env"
      echo "  export AITO_API_KEY=your-key-here"
      echo ""
    fi

    echo ""
    echo "Aito Hacker News demo — run ./do help for available commands"
    echo ""
  '';
}
