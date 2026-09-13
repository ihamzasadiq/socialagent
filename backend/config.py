"""Environment loading and settings for the backend.

There is no database in this app: the whole runtime state lives in one
in-memory session (see orchestrator/session.py). The only configuration is
``backend/.env``, loaded here once at import time for every other module.

The loader is intentionally tiny (KEY=VALUE lines, optional quotes, optional
``export`` prefix) so the backend has no settings-library dependency.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    """Load a .env file into os.environ without overriding real env vars."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip("'\"")
        if name and name not in os.environ:
            os.environ[name] = value


load_env()


class Settings:
    """Runtime settings, read after load_env() so .env values are visible."""

    public_base_url: str = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    frontend_success_url: str = os.environ.get("FRONTEND_SUCCESS_URL", "http://localhost:5173")

    linkedin_client_id: str = os.environ.get("LINKEDIN_CLIENT_ID", "")
    linkedin_client_secret: str = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    # Stable public redirect registered with LinkedIn (e.g. the Supabase edge
    # function bridge). When empty, falls back to PUBLIC_BASE_URL + path.
    linkedin_redirect_uri: str = os.environ.get("LINKEDIN_REDIRECT_URI", "")

    media_dir: Path = BASE_DIR / os.environ.get("MEDIA_DIR", "media")

    @classmethod
    def callback_url(cls, provider: str) -> str:
        """Must match the redirect URL registered with the provider."""
        return f"{cls.public_base_url}/oauth/callback/{provider}"

    @classmethod
    def redirect_uri(cls, provider: str) -> str:
        """The redirect_uri sent to (and back from) the provider.

        LinkedIn uses a stable bridge URL so the registered callback never has
        to change; other providers fall back to PUBLIC_BASE_URL.
        """
        if provider == "linkedin" and cls.linkedin_redirect_uri:
            return cls.linkedin_redirect_uri
        return cls.callback_url(provider)

    @classmethod
    def success_url(cls, provider: str | None = None, error: str | None = None) -> str:
        from urllib.parse import quote

        base = cls.frontend_success_url
        separator = "&" if "?" in base else "?"
        if error is not None:
            return f"{base}{separator}error={quote(error)}"
        return f"{base}{separator}connected={quote(provider or '')}"


settings = Settings()
