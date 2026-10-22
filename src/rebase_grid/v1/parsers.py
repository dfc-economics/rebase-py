"""Helpers that turn raw Rebase JSON payloads into pandas objects.

Centralized here so every timeseries endpoint shares one parsing path. All
timeseries endpoints return column-oriented ``data`` of the form
``{"datetime": [...], "<col>": [...], ...}`` which maps directly onto a
``DataFrame`` indexed by a tz-aware ``DatetimeIndex``.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

import pandas as pd

from ..exceptions import NoMatchingDataError


def parse_columnar(
    data: Mapping[str, Any],
    datetime_key: str = "datetime",
    tz: Optional[str] = "UTC",
) -> pd.DataFrame:
    """Convert columnar ``data`` into a DataFrame indexed by datetime.

    Parameters
    ----------
    data:
        Mapping of column name -> list of values, including a ``datetime``
        column of ISO-8601 timestamps.
    datetime_key:
        Name of the timestamp column to use as the index.
    tz:
        Timezone to convert the index to. ``None`` keeps the parsed tz.

    Raises
    ------
    NoMatchingDataError
        If there are no timestamps in the payload.
    """
    if not data or not data.get(datetime_key):
        raise NoMatchingDataError("The response contained no data rows.")

    frame = pd.DataFrame(dict(data))
    index = pd.to_datetime(frame.pop(datetime_key), utc=True)
    if tz is not None and tz != "UTC":
        index = index.dt.tz_convert(tz)
    frame.index = pd.DatetimeIndex(index, name="datetime")
    return frame


def parse_records(records: List[Mapping[str, Any]]) -> pd.DataFrame:
    """Convert a list of metadata records into a DataFrame.

    Raises
    ------
    NoMatchingDataError
        If the list is empty.
    """
    if not records:
        raise NoMatchingDataError("The response contained no records.")
    return pd.DataFrame.from_records(records)


def parse_time_records(
    records: List[Mapping[str, Any]],
    time_key: str,
    tz: Optional[str] = "UTC",
) -> pd.DataFrame:
    """Convert a list of ``{time_key: ts, ...}`` records into a datetime-indexed
    DataFrame (used for e.g. frequency samples)."""
    if not records:
        raise NoMatchingDataError("The response contained no samples.")
    frame = pd.DataFrame.from_records(records)
    index = pd.to_datetime(frame.pop(time_key), utc=True)
    if tz is not None and tz != "UTC":
        index = index.dt.tz_convert(tz)
    frame.index = pd.DatetimeIndex(index, name=time_key)
    return frame


def parse_exchange_flows(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Parse ``/v1/exchange/flows`` into a datetime-indexed DataFrame.

    The payload holds one entry per counterparty (``exchanges``), each with its
    own columnar ``data``. Value columns are prefixed with the counterparty
    ``zone_key`` when more than one counterparty is present.
    """
    entries = payload.get("exchanges") or []
    if not entries:
        raise NoMatchingDataError("The response contained no exchange data.")

    frames = []
    multi = len(entries) > 1
    for entry in entries:
        frame = parse_columnar(entry["data"])
        if multi:
            frame = frame.add_prefix(f"{entry.get('zone_key', '?')}:")
        frames.append(frame)
    return pd.concat(frames, axis=1)


def parse_grid_capacity(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Parse ``/v1/grid/installed-capacity`` (all zones) into a long-form,
    datetime-indexed DataFrame with a ``zone_key`` column."""
    zones = payload.get("zones") or {}
    if not zones:
        raise NoMatchingDataError("The response contained no zones.")

    frames = []
    for zone_key, block in zones.items():
        frame = parse_columnar(block["data"])
        frame.insert(0, "zone_key", zone_key)
        frames.append(frame)
    return pd.concat(frames, axis=0)
