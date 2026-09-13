"""Shared provider plumbing (ported from the old standalone oauth service).

The app only publishes to LinkedIn today, but the interface is deliberately
provider-shaped so Instagram (or anything else) can slot in by implementing
``Provider`` and being registered in ``distribution/publish.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


class ProviderError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ProviderNotConfigured(ProviderError):
    pass


class ProviderNotSupported(ProviderError):
    pass


class MediaNotSupported(ProviderNotSupported):
    pass


@dataclass(slots=True)
class TokenBundle:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: str | None = None


@dataclass(slots=True)
class Identity:
    external_id: str
    display_name: str | None = None


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def expires_at_from(payload: dict[str, Any], seconds_key: str = "expires_in") -> datetime | None:
    seconds = payload.get(seconds_key)
    if not seconds:
        return None
    return utcnow() + timedelta(seconds=int(seconds))


def error_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


def error_summary(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("error_description", "detail", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value[:200]
        errors = payload.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            message = errors[0].get("message")
            if message:
                return str(message)[:200]
        for key in ("error", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value[:200]
    return str(payload)[:200]


async def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    json: Any = None,
    content: bytes | None = None,
    timeout: float = 30.0,
    expected: tuple[int, ...] | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data,
            json=json,
            content=content,
        )
    allowed = expected or (200, 201, 204)
    if response.status_code not in allowed:
        payload = error_payload(response)
        summary = error_summary(payload)
        message = f"{method} {url} failed with HTTP {response.status_code}"
        if summary:
            message = f"{message}: {summary}"
        raise ProviderError(message, status_code=response.status_code, payload=payload)
    return response


async def request_json(method: str, url: str, **kwargs: Any) -> Any:
    response = await request(method, url, **kwargs)
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(
            f"{method} {url} returned invalid JSON", payload=response.text[:500]
        ) from exc


class Provider(ABC):
    name: str = ""

    @abstractmethod
    def auth_url(self, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str) -> TokenBundle: ...

    @abstractmethod
    async def fetch_identity(self, access_token: str) -> Identity: ...

    @abstractmethod
    async def publish(
        self,
        access_token: str,
        external_id: str,
        text: str,
        image_path: str | None = None,
    ) -> str: ...

    async def revoke(self, access_token: str) -> None:
        return None
