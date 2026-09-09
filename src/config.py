"""Env loading for the demo backend. Fail loud on missing required values
so deployment misconfiguration surfaces at startup, not on the first request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# In production the platform sets env vars directly via App Service settings;
# python-dotenv finds no .env and is a no-op. In local dev it loads ./.env
# with override=True so the file is the source of truth (the nix shell
# also seeds these vars; an explicit .env should win).
load_dotenv(override=True)


@dataclass(frozen=True)
class Config:
    aito_url: str
    aito_key: str
    # Named Aito environment (a branch of master) to query, or None for
    # master. Envs let us rebuild the corpus for a new version of the demo
    # without touching the data production is serving: master stays V1
    # while `AITO_ENV=v2` gets reloaded and tested independently.
    aito_env: str | None = None

    @property
    def api_base(self) -> str:
        """Base URL to hang /api/vN/... off.

        Master is the default env and is only reachable on the unscoped
        path — asking for /env/master/... returns 400.
        """
        if self.aito_env and self.aito_env not in ("master", "env.master"):
            return f"{self.aito_url}/env/{self.aito_env}"
        return self.aito_url


def load_config() -> Config:
    url = os.environ.get("AITO_API_URL")
    key = os.environ.get("AITO_API_KEY")
    if not url or not key:
        raise ValueError(
            "No Aito credentials found. Set AITO_API_URL + AITO_API_KEY in .env "
            "(copy from .env.example to get started)."
        )
    env = (os.environ.get("AITO_ENV") or "").strip() or None
    return Config(aito_url=url.rstrip("/"), aito_key=key, aito_env=env)
