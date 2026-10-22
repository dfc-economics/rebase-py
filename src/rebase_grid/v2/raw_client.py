"""Low-level Rebase Grid **v2** client returning raw JSON.

The v2 API models the grid as a tree of *entities* (synchronous areas,
countries, price zones, borders, ...) that hold *timeseries*, each identified by
a dotted name (``category.sub_category.definition[.component]``) and a
provider. Typical workflow: discover entities / series, describe a series, then
read its values — optionally as they were known at some past time (``as_of``).

Every method returns the decoded JSON exactly as the API sends it. See
:class:`rebase_grid.v2.pandas_client.RebasePandasClient` for DataFrames.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional, Union

from .._http import BaseClient
from ..decorators import DateLike, normalize_as_of, to_rfc3339_utc

DEFAULT_BASE_URL = "https://grid-api-ffcps6p2ra-ey.a.run.app/v2"


def _quote(segment: str) -> str:
    """Path segments (entity ids, series names) may hold characters like ``>``."""
    from urllib.parse import quote

    return quote(str(segment), safe="")


def _time_of_day(value: Any) -> Optional[str]:
    if value is None or isinstance(value, str):
        return value
    return value.strftime("%H:%M")  # datetime.time / datetime


class RebaseRawClient(BaseClient):
    """Thin HTTP wrapper over the Rebase Grid v2 API returning raw JSON."""

    default_base_url = DEFAULT_BASE_URL

    # ================================================================== #
    # Account
    # ================================================================== #
    def get_version(self) -> dict:
        """``GET /version`` — build and search-index information."""
        return self._get("/version")

    def get_account(self) -> dict:
        """``GET /me`` — the account the API key belongs to."""
        return self._get("/me")

    # ================================================================== #
    # Discover
    # ================================================================== #
    def get_entity_tree(self, geo: Optional[bool] = None) -> dict:
        """``GET /entities`` — the full entity tree (nested ``children``)."""
        return self._get("/entities", {"geo": _bool(geo)})

    def get_entity(self, entity: str, geo: Optional[bool] = None) -> dict:
        """``GET /entities/{entity}`` — one entity: parent, children, relations,
        and a summary of its timeseries (counts by provider and category)."""
        return self._get(f"/entities/{_quote(entity)}", {"geo": _bool(geo)})

    def list_entity_timeseries(
        self,
        entity: str,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        q: Optional[str] = None,
        data_type: Optional[str] = None,
    ) -> dict:
        """``GET /entities/{entity}/timeseries`` — series available on an entity.

        Filter by ``provider``, ``category`` (first name segment), free-text
        ``q``, or ``data_type`` (``actual|forecast|price|capacity|schedule|other``).
        """
        params = {
            "provider": provider,
            "category": category,
            "q": q,
            "data_type": data_type,
        }
        return self._get(f"/entities/{_quote(entity)}/timeseries", params)

    def search_timeseries(
        self,
        q: Optional[str] = None,
        entity: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        provider: Optional[str] = None,
        data_type: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict:
        """``GET /timeseries`` — search series across all entities (one page).

        Returns ``{"total", "items", "next"}``; pass ``next`` back as ``cursor``
        for the following page, or use :meth:`iter_search_timeseries`.
        """
        params = {
            "q": q,
            "entity": entity,
            "category": category,
            "subcategory": subcategory,
            "provider": provider,
            "data_type": data_type,
            "limit": limit,
            "cursor": cursor,
        }
        return self._get("/timeseries", params)

    def iter_search_timeseries(self, limit: int = 1000, **filters: Any) -> Iterator[dict]:
        """Yield every search result item, following ``next`` cursors."""
        cursor: Optional[str] = None
        while True:
            # Explicit base-class call: subclasses override search_timeseries.
            page = RebaseRawClient.search_timeseries(
                self, limit=limit, cursor=cursor, **filters
            )
            yield from page.get("items", [])
            cursor = page.get("next")
            if not cursor:
                return

    def list_plants(
        self,
        entity: str,
        technology: Optional[str] = None,
        min_mw: Optional[float] = None,
        has_timeseries: Optional[bool] = None,
        bbox: Optional[str] = None,
        cursor: Optional[str] = None,
    ) -> dict:
        """``GET /entities/{entity}/plants`` — plants located in an entity.

        NB: the server currently answers ``501`` (plants hold no series yet),
        which surfaces as :class:`~rebase_grid.exceptions.EndpointNotImplementedError`.
        """
        params = {
            "technology": technology,
            "min_mw": min_mw,
            "has_timeseries": _bool(has_timeseries),
            "bbox": bbox,
            "cursor": cursor,
        }
        return self._get(f"/entities/{_quote(entity)}/plants", params)

    # ================================================================== #
    # Describe
    # ================================================================== #
    def get_timeseries_metadata(self, entity: str, name: str) -> dict:
        """``GET /entities/{entity}/timeseries/{name}`` — definition, unit, and
        one block per provider (resolution, extent, latency, coverage)."""
        return self._get(f"/entities/{_quote(entity)}/timeseries/{_quote(name)}")

    # ================================================================== #
    # Read
    # ================================================================== #
    def query_values(
        self,
        entity: str,
        name: str,
        provider: str,
        start: DateLike,
        end: DateLike,
        as_of: Union[None, str, DateLike] = None,
        at: Any = None,
        max_snapshots: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> dict:
        """``GET /entities/{entity}/timeseries/{name}/values`` — one page.

        Parameters
        ----------
        provider:
            Required, even when only one provider publishes the series.
        start, end:
            Inclusive window. Naive values are interpreted as UTC. At most
            100,000 points per request at the series' resolution.
        as_of:
            Which version of each value to return. ``None`` = latest; an
            instant = values as known then; an ISO 8601 duration (``"PT1H"``,
            ``"P1D"``) = one snapshot per period; ``"rolling"`` = one snapshot
            per native step. Duration/rolling responses hold ``snapshots``.
        at:
            Time of day (``"10:00"``) anchoring duration snapshots.
        max_snapshots, cursor:
            Paging for snapshot responses (``next`` in the response).
        """
        params: Dict[str, Any] = {
            "provider": provider,
            "start": to_rfc3339_utc(start),
            "end": to_rfc3339_utc(end),
            "as_of": normalize_as_of(as_of),
            "at": _time_of_day(at),
            "max_snapshots": max_snapshots,
            "cursor": cursor,
        }
        return self._get(
            f"/entities/{_quote(entity)}/timeseries/{_quote(name)}/values", params
        )

    def iter_values_pages(self, *args: Any, **kwargs: Any) -> Iterator[dict]:
        """Yield :meth:`query_values` pages, following ``next`` for snapshots."""
        kwargs.pop("cursor", None)
        cursor: Optional[str] = None
        while True:
            # Explicit base-class call: subclasses override query_values.
            page = RebaseRawClient.query_values(self, *args, cursor=cursor, **kwargs)
            yield page
            cursor = page.get("next")
            if not cursor:
                return


def _bool(value: Optional[bool]) -> Optional[str]:
    return None if value is None else ("true" if value else "false")
