"""Shared HTTP plumbing for the Rebase Grid clients (all API versions).

Handles authentication, retry/backoff (honouring ``Retry-After``), and mapping
of HTTP errors onto the :mod:`rebase_grid.exceptions` hierarchy. Version
specific clients subclass :class:`BaseClient` and only add endpoint methods.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .decorators import clean_params
from .exceptions import (
    AuthenticationError,
    EndpointNotImplementedError,
    InvalidParameterError,
    NotFoundError,
    RateLimitError,
    RebaseConfigError,
    RebaseHTTPError,
    ServiceUnavailableError,
)

API_KEY_ENV_VAR = "REBASE_API_KEY"

# Statuses worth retrying with backoff (transient server / rate-limit errors).
# urllib3 honours the Retry-After header on 429 / 503 automatically.
_RETRY_STATUSES = (429, 500, 502, 503, 504)


class BaseClient:
    """Authenticated ``requests`` session with retries and error mapping.

    Parameters
    ----------
    api_key:
        Rebase API token. If omitted, it is read from the ``REBASE_API_KEY``
        environment variable (a local ``.env`` is loaded automatically).
    session:
        Optional pre-configured :class:`requests.Session`.
    base_url:
        API root. Defaults to the subclass's ``default_base_url``.
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Automatic retries for transient errors (429/5xx).
    """

    default_base_url: str = ""

    def __init__(
        self,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        if api_key is None:
            load_dotenv()
            api_key = os.getenv(API_KEY_ENV_VAR)
        if not api_key:
            raise RebaseConfigError(
                "No API key provided. Pass api_key=... or set the "
                f"{API_KEY_ENV_VAR} environment variable (e.g. in a .env file)."
            )

        self.api_key = api_key
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.timeout = timeout
        self.session = session or self._build_session(max_retries)
        self.session.headers.update(
            {"X-API-Key": self.api_key, "Accept": "application/json"}
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=_RETRY_STATUSES,
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """GET ``path`` and return decoded JSON; raise mapped errors on failure."""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(
                url, params=clean_params(params or {}), timeout=self.timeout
            )
        except requests.RequestException as exc:  # network-level failure
            raise RebaseHTTPError(f"Request to {url} failed: {exc}") from exc

        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return

        status = response.status_code
        body = _json_or_none(response)
        extra: dict = {}
        if isinstance(body, dict):
            # v2 error body: {"error", "message", "param"?, "closest"?, "providers"?}
            extra = {
                "param": body.get("param"),
                "closest": body.get("closest"),
                "providers": body.get("providers"),
            }
        retry_after = _parse_retry_after(response)
        message = f"{status} {response.reason} for {response.url}: {_describe(body, response)}"
        args = (message, status, response)
        kwargs = dict(retry_after=retry_after, **extra)

        if status in (401, 403):
            raise AuthenticationError(*args, **kwargs)
        if status == 404:
            raise NotFoundError(*args, **kwargs)
        if status in (400, 422):
            raise InvalidParameterError(*args, **kwargs)
        if status == 429:
            raise RateLimitError(*args, **kwargs)
        if status == 501:
            raise EndpointNotImplementedError(*args, **kwargs)
        if status == 503:
            raise ServiceUnavailableError(*args, **kwargs)
        raise RebaseHTTPError(*args, **kwargs)

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _json_or_none(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _parse_retry_after(response: requests.Response) -> Optional[float]:
    value = response.headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _describe(body: Any, response: requests.Response) -> str:
    """Best-effort human-readable error text from a v1 or v2 error body."""
    if isinstance(body, dict):
        if "message" in body:  # v2
            return str(body["message"])
        if "detail" in body:  # v1
            return str(body["detail"])
        return str(body)[:500]
    if body is not None:
        return str(body)[:500]
    return response.text[:500]
