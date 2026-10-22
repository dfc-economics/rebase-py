"""Pandas-returning Rebase Grid **v2** client.

Conventions
-----------
- **Values** come back as a DataFrame indexed by ``valid_time`` (tz-aware UTC)
  with columns ``value``, ``knowledge_time`` and ``annotation``. Series-level
  metadata (unit, resolution, provider, ...) is attached to ``.attrs``.
- With ``as_of`` set to a duration or ``"rolling"`` the result is a long frame
  with a ``(as_of, valid_time)`` MultiIndex — one row per snapshot and value —
  which ``.unstack("as_of")`` turns into a vintage matrix.
- **Discovery** endpoints return DataFrames (one row per entity / series).
- Windows above the API's 100,000-point limit are split automatically.
- Empty results raise :class:`~rebase_grid.exceptions.NoMatchingDataError`.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Union

import pandas as pd

from ..decorators import DateLike, to_rfc3339_utc
from ..exceptions import InvalidParameterError, NoMatchingDataError
from .raw_client import RebaseRawClient

_POINT_COLUMNS = ["valid_time", "value", "knowledge_time", "annotation"]


class RebasePandasClient(RebaseRawClient):
    """Rebase Grid v2 client that returns pandas objects."""

    # ------------------------------------------------------------------ #
    # Account
    # ------------------------------------------------------------------ #
    def get_version(self) -> pd.Series:
        """``GET /version`` -> Series."""
        return pd.Series(super().get_version())

    def get_account(self) -> pd.Series:
        """``GET /me`` -> Series (email, name)."""
        return pd.Series(super().get_account())

    # ------------------------------------------------------------------ #
    # Discover
    # ------------------------------------------------------------------ #
    def get_entity_tree(self, geo: Optional[bool] = None) -> pd.DataFrame:
        """``GET /entities`` -> flat DataFrame: ``id, kind, name, parent, depth,
        timeseries`` (one row per entity, tree order)."""
        rows: List[dict] = []

        def walk(nodes: Iterable[dict], parent: Optional[str], depth: int) -> None:
            for node in nodes:
                rows.append(
                    {
                        "id": node["id"],
                        "kind": node.get("kind"),
                        "name": node.get("name"),
                        "parent": parent,
                        "depth": depth,
                        "timeseries": node.get("timeseries"),
                    }
                )
                walk(node.get("children") or [], node["id"], depth + 1)

        walk(super().get_entity_tree(geo=geo).get("entities", []), None, 0)
        return pd.DataFrame(rows, columns=["id", "kind", "name", "parent", "depth", "timeseries"])

    def get_entity(self, entity: str, geo: Optional[bool] = None) -> pd.Series:
        """``GET /entities/{entity}`` -> Series of the entity's fields."""
        return pd.Series(super().get_entity(entity, geo=geo))

    def list_entity_timeseries(
        self,
        entity: str,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        q: Optional[str] = None,
        data_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """``GET /entities/{entity}/timeseries`` -> DataFrame ``name, provider,
        data_type``."""
        payload = super().list_entity_timeseries(
            entity, provider=provider, category=category, q=q, data_type=data_type
        )
        frame = pd.DataFrame(
            payload.get("timeseries", []), columns=["name", "provider", "data_type"]
        )
        frame.attrs["entity"] = entity
        return frame

    def search_timeseries(  # type: ignore[override]
        self,
        q: Optional[str] = None,
        entity: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        provider: Optional[str] = None,
        data_type: Optional[str] = None,
        max_results: Optional[int] = None,
        page_size: int = 1000,
    ) -> pd.DataFrame:
        """``GET /timeseries`` -> DataFrame ``entity, name, provider,
        data_type`` across *all* result pages (capped by ``max_results``)."""
        items: List[dict] = []
        for item in self.iter_search_timeseries(
            limit=page_size, q=q, entity=entity, category=category,
            subcategory=subcategory, provider=provider, data_type=data_type,
        ):
            items.append({k: item.get(k) for k in ("entity", "name", "provider", "data_type")})
            if max_results is not None and len(items) >= max_results:
                break
        return pd.DataFrame(items, columns=["entity", "name", "provider", "data_type"])

    def list_plants(self, entity: str, **filters: Any) -> pd.DataFrame:  # type: ignore[override]
        """``GET /entities/{entity}/plants`` -> DataFrame of plants."""
        payload = super().list_plants(entity, **filters)
        return pd.DataFrame(payload.get("plants", []))

    # ------------------------------------------------------------------ #
    # Describe
    # ------------------------------------------------------------------ #
    def get_timeseries_metadata(self, entity: str, name: str) -> pd.DataFrame:  # type: ignore[override]
        """``GET /entities/{entity}/timeseries/{name}`` -> one row per provider.

        Columns: ``provider, resolution, first, last, latency_p05/p50/p95
        (minutes), coverage, publication_time``. The series definition, unit
        and data type are in ``.attrs``.
        """
        payload = super().get_timeseries_metadata(entity, name)
        rows = []
        for p in payload.get("providers", []):
            extent = p.get("extent") or {}
            latency = p.get("latency_minutes") or {}
            rows.append(
                {
                    "provider": p.get("provider"),
                    "resolution": p.get("resolution"),
                    "first": pd.to_datetime(extent.get("first"), utc=True),
                    "last": pd.to_datetime(extent.get("last"), utc=True),
                    "latency_p05": latency.get("p05"),
                    "latency_p50": latency.get("p50"),
                    "latency_p95": latency.get("p95"),
                    "coverage": p.get("coverage"),
                    "publication_time": p.get("publication_time"),
                }
            )
        frame = pd.DataFrame(rows)
        frame.attrs.update(
            entity=payload.get("entity"),
            name=payload.get("name"),
            unit=payload.get("unit"),
            data_type=payload.get("data_type"),
            definition=payload.get("definition"),
            component=payload.get("component"),
        )
        return frame

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def query_values(  # type: ignore[override]
        self,
        entity: str,
        name: str,
        provider: str,
        start: DateLike,
        end: DateLike,
        as_of: Union[None, str, DateLike] = None,
        at: Any = None,
        max_snapshots: Optional[int] = None,
    ) -> pd.DataFrame:
        """Values of one series as a DataFrame (see module docstring).

        ``as_of=None`` (latest) or an instant -> index ``valid_time``.
        ``as_of`` a duration (``"PT1H"``) or ``"rolling"`` -> MultiIndex
        ``(as_of, valid_time)``. Parameters are described on
        :meth:`RebaseRawClient.query_values`.
        """
        snapshot_mode = isinstance(as_of, str) and (as_of == "rolling" or as_of.startswith("P"))
        if snapshot_mode:
            return self._query_snapshots(
                entity, name, provider, start, end, as_of, at, max_snapshots
            )
        meta, frame = self._query_flat(entity, name, provider, start, end, as_of)
        if frame.empty:
            raise NoMatchingDataError(
                f"No values for {entity}/{name} [{provider}] in the requested window."
            )
        frame.attrs.update(meta)
        return frame

    def query_series(
        self,
        entity: str,
        name: str,
        provider: str,
        start: DateLike,
        end: DateLike,
        as_of: Union[None, str, DateLike] = None,
    ) -> pd.Series:
        """Like :meth:`query_values` but only the ``value`` column, as a Series
        named ``"<provider>:<name>"`` (flat mode only)."""
        frame = self.query_values(entity, name, provider, start, end, as_of=as_of)
        series = frame["value"].astype(float)
        series.name = f"{provider}:{name}"
        series.attrs.update(frame.attrs)
        return series

    # -- internals ------------------------------------------------------ #
    def _query_flat(self, entity, name, provider, start, end, as_of):
        """Fetch a flat window, bisecting it if it exceeds the point limit."""
        try:
            payload = super().query_values(entity, name, provider, start, end, as_of=as_of)
        except InvalidParameterError as exc:
            lo, hi = pd.Timestamp(to_rfc3339_utc(start)), pd.Timestamp(to_rfc3339_utc(end))
            too_big = exc.param == "end" and "points" in str(exc)
            if not too_big or (hi - lo) <= pd.Timedelta(minutes=2):
                raise
            mid = lo + (hi - lo) / 2
            meta, left = self._query_flat(entity, name, provider, lo, mid, as_of)
            _, right = self._query_flat(entity, name, provider, mid, hi, as_of)
            both = pd.concat([left, right])
            return meta, both[~both.index.duplicated(keep="first")]
        return _flat_meta(payload), _points_frame(payload.get("points", []))

    def _query_snapshots(self, entity, name, provider, start, end, as_of, at, max_snapshots):
        frames = []
        meta: dict = {}
        for page in self.iter_values_pages(
            entity, name, provider, start, end, as_of=as_of, at=at, max_snapshots=max_snapshots
        ):
            meta = _flat_meta(page)
            for snap in page.get("snapshots", []):
                frame = _points_frame(snap.get("points", []))
                if frame.empty:
                    continue
                frame["as_of"] = pd.to_datetime(snap["as_of"], utc=True)
                frames.append(frame.reset_index())
        if not frames:
            raise NoMatchingDataError(
                f"No snapshots for {entity}/{name} [{provider}] in the requested window."
            )
        out = pd.concat(frames, ignore_index=True).set_index(["as_of", "valid_time"])
        out.attrs.update(meta)
        return out


def _flat_meta(payload: dict) -> dict:
    return {
        k: payload.get(k)
        for k in ("entity", "name", "provider", "unit", "resolution", "publication_time", "as_of")
    }


def _points_frame(points: List[dict]) -> pd.DataFrame:
    if not points:
        return pd.DataFrame(columns=_POINT_COLUMNS[1:], index=pd.DatetimeIndex([], tz="UTC", name="valid_time"))
    frame = pd.DataFrame(points, columns=_POINT_COLUMNS)
    frame["valid_time"] = pd.to_datetime(frame["valid_time"], utc=True)
    frame["knowledge_time"] = pd.to_datetime(frame["knowledge_time"], utc=True)
    return frame.set_index("valid_time")
