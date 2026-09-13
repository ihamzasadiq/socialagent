"""Test bootstrap: make sure the backend package is importable and the
OpenRouter key is forced empty so generation uses the offline fixtures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Set BEFORE config is imported: load_env() never overrides existing names,
# so an empty value here keeps backend/.env's real key out of the tests.
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["LINKEDIN_REDIRECT_URI"] = ""
os.environ.setdefault("LINKEDIN_CLIENT_ID", "test-client")
os.environ.setdefault("LINKEDIN_CLIENT_SECRET", "test-secret")
os.environ.setdefault("PUBLIC_BASE_URL", "https://test.example.com")
os.environ.setdefault("FRONTEND_SUCCESS_URL", "http://localhost:5173")
