"""Pandas-returning Rebase Grid client.

``RebasePandasClient`` subclasses :class:`RebaseRawClient` and overrides the
endpoint methods to parse raw JSON into pandas ``DataFrame`` / ``Series``
objects, following the ``entsoe-py`` ``EntsoePandasClient`` pattern.

Conventions
-----------
- **Timeseries** endpoints return a datetime-indexed (tz-aware, UTC)
  ``DataFrame``; single-value series (price, consumption) return a ``Series``.
  Top-level metadata (source, currency, units, ...) is attached to ``.attrs``.
- **Collection metadata** (zones, sources, coverage, geo datasets) returns a
  ``DataFrame``.
- **Single-entity metadata** (a zone, an exchange pair) returns a ``Series``.
- **Geo feature** endpoints return the raw GeoJSON ``dict`` (drop straight into
  geopandas); only the dataset *listing* is tabularised.
- The documented-but-undeployed stubs are inherited unchanged and raise
  :class:`~rebase_grid.exceptions.EndpointNotDeployedError`.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .decorators import DateLike
from .parsers import (
    parse_columnar,
    parse_exchange_flows,
    parse_grid_capacity,
    parse_records,
    parse_time_records,
)
from .raw_client import RebaseRawClient


def _attach(obj, payload: dict, *keys: str):
    """Copy selected top-level payload fields onto ``obj.attrs``."""
    obj.attrs.update({k: payload.get(k) for k in keys})
    return obj


class RebasePandasClient(RebaseRawClient):
    """Rebase Grid client that returns pandas objects."""

    # ------------------------------------------------------------------ #
    # Zones (metadata)
    # ------------------------------------------------------------------ #
    def list_zones(self) -> pd.DataFrame:
        """``GET /v1/zone/list`` -> DataFrame, one row per zone."""
        return parse_records(super().list_zones().get("zones", []))

    def get_zone(self, zone_key: str) -> pd.Series:
        """``GET /v1/zone/get/{zone_key}`` -> Series of the zone's metadata."""
        return pd.Series(super().get_zone(zone_key))

    def get_zone_coverage(self, zone_key: str) -> pd.DataFrame:
        """``GET /v1/zone/{zone_key}/coverage`` -> DataFrame of coverage series."""
        payload = super().get_zone_coverage(zone_key)
        return _attach(parse_records(payload.get("series", [])), payload,
                       "zone_key", "resolution", "start", "end")

    def get_zone_sources(self, zone_key: str) -> pd.DataFrame:
        """``GET /v1/zone/{zone_key}/sources`` -> DataFrame of sources."""
        return parse_records(super().get_zone_sources(zone_key).get("sources", []))

    def list_sources(self, zone_key: str) -> pd.DataFrame:
        """``GET /v1/sources`` -> DataFrame of (source, variable) pairs."""
        return parse_records(super().list_sources(zone_key).get("sources", []))

    # ------------------------------------------------------------------ #
    # Timeseries
    # ------------------------------------------------------------------ #
    def query_production(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        resolution: Optional[str] = None,
        fuel: Optional[str] = None,
    ) -> pd.DataFrame:
        """``GET /v1/zone/{zone_key}/production`` -> DataFrame (one col per fuel)."""
        payload = super().query_production(
            zone_key, start=start, end=end, source=source,
            resolution=resolution, fuel=fuel,
        )
        return _attach(parse_columnar(payload["data"]), payload,
                       "zone_key", "source", "resolution")

    def query_price(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> pd.Series:
        """``GET /v1/zone/{zone_key}/price`` -> price Series (currency in attrs)."""
        payload = super().query_price(zone_key, start=start, end=end, source=source)
        series = parse_columnar(payload["data"])["price"]
        series.name = "price"
        return _attach(series, payload, "currency", "source", "zone_key")

    def query_consumption(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> pd.Series:
        """``GET /v1/zone/{zone_key}/consumption`` -> load Series (MW)."""
        payload = super().query_consumption(zone_key, start=start, end=end, source=source)
        frame = parse_columnar(payload["data"])
        # Single load column ("load_mw"); return it as a named Series.
        col = frame.columns[0]
        series = frame[col]
        return _attach(series, payload, "source", "zone_key")

    def query_storage(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> pd.DataFrame:
        """``GET /v1/zone/{zone_key}/storage`` -> DataFrame (one col per type)."""
        payload = super().query_storage(zone_key, start=start, end=end, source=source)
        return _attach(parse_columnar(payload["data"]), payload, "source", "zone_key")

    def query_installed_capacity(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        breakdown: Optional[str] = None,
    ) -> pd.DataFrame:
        """``GET /v1/zone/{zone_key}/installed-capacity`` -> DataFrame (MW)."""
        payload = super().query_installed_capacity(
            zone_key, start=start, end=end, source=source, breakdown=breakdown
        )
        return _attach(parse_columnar(payload["data"]), payload,
                       "unit", "breakdown", "source", "zone_key")

    def query_grid_installed_capacity(
        self,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
    ) -> pd.DataFrame:
        """``GET /v1/grid/installed-capacity`` -> long DataFrame with ``zone_key``."""
        payload = super().query_grid_installed_capacity(start=start, end=end)
        return _attach(parse_grid_capacity(payload), payload, "unit")

    # ------------------------------------------------------------------ #
    # Exchange
    # ------------------------------------------------------------------ #
    def list_exchanges(self) -> pd.Series:
        """``GET /v1/exchange/list`` -> Series of ``A->B`` exchange keys."""
        keys = super().list_exchanges().get("exchanges", [])
        return pd.Series(keys, name="exchange_key")

    def get_exchange(self, exchange_key: str) -> pd.Series:
        """``GET /v1/exchange/get/{exchange_key}`` -> Series of pair metadata."""
        return pd.Series(super().get_exchange(exchange_key))

    def get_exchange_coverage(self, exchange_key: str) -> pd.DataFrame:
        """``GET /v1/exchange/{exchange_key}/coverage`` -> DataFrame of series."""
        payload = super().get_exchange_coverage(exchange_key)
        return parse_records(payload.get("series", []))

    def get_exchange_sources(self, exchange_key: str) -> pd.DataFrame:
        """``GET /v1/exchange/{exchange_key}/sources`` -> DataFrame of sources."""
        payload = super().get_exchange_sources(exchange_key)
        return parse_records(payload.get("sources", []))

    def query_exchange_flows(
        self,
        key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> pd.DataFrame:
        """``GET /v1/exchange/flows/{key}`` -> DataFrame of physical flows (MW)."""
        payload = super().query_exchange_flows(
            key, start=start, end=end, source=source, resolution=resolution
        )
        return _attach(parse_exchange_flows(payload), payload, "source", "resolution")

    def query_transfer_capacity(
        self,
        from_zone: str,
        to_zone: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
    ) -> pd.DataFrame:
        """``GET /v1/exchange/capacity/{from}/{to}`` -> DataFrame of NTC series.

        Returns an empty DataFrame when the pair has no capacity data in the
        window (the API responds ``200`` with an empty ``series``).
        """
        payload = super().query_transfer_capacity(from_zone, to_zone, start=start, end=end)
        series = payload.get("series", [])
        frame = pd.DataFrame.from_records(series) if series else pd.DataFrame()
        return _attach(frame, payload, "from_zone", "to_zone", "canonical_edge")

    # ------------------------------------------------------------------ #
    # Frequency
    # ------------------------------------------------------------------ #
    def get_frequency_live(self) -> pd.DataFrame:
        """``GET /v1/frequency/live`` -> datetime-indexed DataFrame of Hz samples."""
        payload = super().get_frequency_live()
        frame = parse_time_records(payload.get("samples", []), time_key="t")
        return _attach(frame, payload, "area", "fetched_at")

    # ------------------------------------------------------------------ #
    # Geo — dataset listing is tabularised; feature payloads stay GeoJSON.
    # ------------------------------------------------------------------ #
    def list_geo_datasets(self) -> pd.DataFrame:
        """``GET /v1/geo`` -> DataFrame of registered geo datasets."""
        return parse_records(super().list_geo_datasets().get("datasets", []))
