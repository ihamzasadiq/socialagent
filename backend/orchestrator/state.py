"""Small helpers shared across routes.py. NOT a persistence layer — the
orchestrator is stateless per request by design (see orchestrator/README.md
and shared/README.md for why). Nothing here stores anything across calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
