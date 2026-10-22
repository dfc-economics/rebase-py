"""Exception hierarchy for the Rebase Grid client.

All errors raised by the clients derive from :class:`RebaseError`, so callers
can catch everything with a single ``except RebaseError``.
"""

from __future__ import annotations

from typing import List, Optional

import requests


class RebaseError(Exception):
    """Base class for all errors raised by the Rebase Grid client."""


class RebaseConfigError(RebaseError):
    """Raised for client misconfiguration (e.g. a missing API key)."""


class RebaseHTTPError(RebaseError):
    """Raised when the API returns a non-2xx status.

    Attributes
    ----------
    status_code:
        The HTTP status code returned by the API.
    response:
        The underlying :class:`requests.Response`, if available.
    param:
        The offending request parameter (API v2 ``400`` errors).
    closest:
        Closest matching ids/names (API v2 ``404`` errors) — handy for typos.
    providers:
        Valid providers for a series (API v2 ``400`` provider errors).
    retry_after:
        Seconds to wait before retrying, from the ``Retry-After`` header
        (``429`` / ``503``).
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: "Optional[requests.Response]" = None,
        *,
        param: Optional[str] = None,
        closest: Optional[List[str]] = None,
        providers: Optional[List[str]] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.param = param
        self.closest = closest
        self.providers = providers
        self.retry_after = retry_after


class AuthenticationError(RebaseHTTPError):
    """Raised on ``401`` / ``403`` — missing, invalid, or unauthorized API key."""


class InvalidParameterError(RebaseHTTPError):
    """Raised on ``400`` / ``422`` — request parameters failed validation."""


class NotFoundError(RebaseHTTPError):
    """Raised on ``404`` — the requested entity/series/zone does not exist."""


class RateLimitError(RebaseHTTPError):
    """Raised on ``429`` — too many requests (after retries are exhausted)."""


class EndpointNotImplementedError(RebaseHTTPError):
    """Raised on ``501`` — the endpoint is documented but not implemented yet."""


class ServiceUnavailableError(RebaseHTTPError):
    """Raised on ``503`` — platform unavailable or index still warming up."""


class NoMatchingDataError(RebaseError):
    """Raised when the API responds successfully but contains no data rows."""
