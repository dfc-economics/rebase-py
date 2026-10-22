"""rebase-grid — Python client for the Rebase Grid API.

Two clients, following the entsoe-py pattern:

- :class:`RebaseRawClient` returns raw JSON (dicts/lists).
- :class:`RebasePandasClient` returns pandas ``DataFrame`` / ``Series``.

The top-level clients target API **v2**. The earlier v1 API remains available as
:mod:`rebase_grid.v1`.

Example
-------
>>> from rebase_grid import RebasePandasClient
>>> client = RebasePandasClient()  # reads REBASE_API_KEY from env / .env
>>> client.search_timeseries(q="load", entity="IT-NO")
>>> client.query_values("IT-NO", "consumption.realised_load.total_load",
...                     provider="entsoe", start="2026-10-01", end="2026-10-02")
"""

from __future__ import annotations

from .exceptions import (
    AuthenticationError,
    EndpointNotImplementedError,
    InvalidParameterError,
    NoMatchingDataError,
    NotFoundError,
    RateLimitError,
    RebaseConfigError,
    RebaseError,
    RebaseHTTPError,
    ServiceUnavailableError,
)
from .v2 import RebasePandasClient, RebaseRawClient

__version__ = "0.3.0"

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
    "EndpointNotImplementedError",
    "ServiceUnavailableError",
    "NoMatchingDataError",
    "__version__",
]
