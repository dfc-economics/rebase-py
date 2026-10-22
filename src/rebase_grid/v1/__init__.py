"""Rebase Grid API v1 clients (zone / area / asset endpoints) — legacy.

Kept for existing code; new code should use the top-level v2 clients
(``from rebase_grid import RebasePandasClient``).
"""

from __future__ import annotations

from .pandas_client import RebasePandasClient
from .raw_client import DEFAULT_BASE_URL, RebaseRawClient

__all__ = ["RebaseRawClient", "RebasePandasClient", "DEFAULT_BASE_URL"]
