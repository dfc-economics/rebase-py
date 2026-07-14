"""Parameter-coercion helpers shared by the clients.

Kept separate from the client so the same normalization logic is reused by
every endpoint method (and is easy to unit-test in isolation).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping, Optional, Union

import pandas as pd

DateLike = Union[str, date, datetime, pd.Timestamp]


def to_iso8601(value: Optional[DateLike]) -> Optional[str]:
    """Coerce a date-like value to an ISO-8601 string the API accepts.

    Accepts ``str`` (returned unchanged), ``datetime``/``date``, or
    :class:`pandas.Timestamp`. Naive datetimes are assumed to be UTC. ``None``
    passes through as ``None`` so optional params can be dropped downstream.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.isoformat()


def clean_params(params: Mapping[str, Any]) -> dict:
    """Drop ``None`` values so optional query params are simply omitted."""
    return {k: v for k, v in params.items() if v is not None}
