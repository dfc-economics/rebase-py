"""rebase-grid — Python client for the Rebase Grid API.

Two clients, following the entsoe-py pattern:

- :class:`RebaseRawClient` returns raw JSON (dicts/lists).
- :class:`RebasePandasClient` returns pandas ``DataFrame`` / ``Series``.

Example
-------
>>> from rebase_grid import RebasePandasClient
>>> client = RebasePandasClient()  # reads REBASE_API_KEY from env / .env
>>> client.list_areas().head()
>>> client.query_price("DE", start="2024-01-01", end="2024-01-02")
"""

from __future__ import annotations

from .exceptions import (
    AuthenticationError,
    InvalidParameterError,
    NoMatchingDataError,
    NotFoundError,
    RateLimitError,
    RebaseConfigError,
    RebaseError,
    RebaseHTTPError,
)
from .pandas_client import RebasePandasClient
from .raw_client import RebaseRawClient

__version__ = "0.2.0"

__all__ = [
    "RebaseRawClient",
    "RebasePandasClient",
    "RebaseError",
    "RebaseConfigError",
    "RebaseHTTPError",
    "AuthenticationError",
    "InvalidParameterError",
    "NotFoundError",
    "RateLimitError",
    "NoMatchingDataError",
    "__version__",
]
