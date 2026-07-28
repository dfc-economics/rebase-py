"""Exception hierarchy for the Rebase Grid client.

All errors raised by the clients derive from :class:`RebaseError`, so callers
can catch everything with a single ``except RebaseError``.
"""

from __future__ import annotations

from typing import Optional

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
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: "Optional[requests.Response]" = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(RebaseHTTPError):
    """Raised on ``401`` / ``403`` — missing, invalid, or unauthorized API key."""


class InvalidParameterError(RebaseHTTPError):
    """Raised on ``422`` — request parameters failed validation."""


class NotFoundError(RebaseHTTPError):
    """Raised on ``404`` — the requested zone/area/asset does not exist."""


class RateLimitError(RebaseHTTPError):
    """Raised on ``429`` — too many requests (after retries are exhausted)."""


class NoMatchingDataError(RebaseError):
    """Raised when the API responds successfully but contains no data rows."""
