"""Parameter-coercion helpers shared by the clients.

Kept separate from the client so the same normalization logic is reused by
every endpoint method (and is easy to unit-test in isolation).
"""

from __future__ import annotations

import re
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


def to_rfc3339_utc(value: Optional[DateLike]) -> Optional[str]:
    """Coerce a date-like value to an RFC 3339 UTC string (``...Z``).

    The v2 API rejects timestamps without a UTC offset, so naive values
    (including bare dates such as ``"2026-10-01"``) are interpreted as UTC and
    tz-aware values are converted to UTC. ``None`` passes through.
    """
    if value is None:
        return None
    ts = pd.Timestamp(value)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.isoformat().replace("+00:00", "Z")


_DURATION_RE = re.compile(r"^P(?=\d|T\d)(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?$")


def normalize_as_of(value: Any) -> Optional[str]:
    """Normalise the v2 ``as_of`` argument.

    Accepts ``None`` (latest), the literal ``"rolling"``, an ISO 8601 duration
    (``"PT1H"``, ``"P1D"``) which are passed through unchanged, or any
    date-like instant, which is converted to RFC 3339 UTC.
    """
    if value is None or value == "rolling":
        return value
    if isinstance(value, str) and _DURATION_RE.match(value):
        return value
    return to_rfc3339_utc(value)


def clean_params(params: Mapping[str, Any]) -> dict:
    """Drop ``None`` values so optional query params are simply omitted."""
    return {k: v for k, v in params.items() if v is not None}
