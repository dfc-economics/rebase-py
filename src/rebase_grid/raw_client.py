"""Low-level Rebase Grid client returning raw JSON.

``RebaseRawClient`` mirrors ``entsoe-py``'s ``EntsoeRawClient``: it handles
authentication, retries, and error mapping, and every endpoint method returns
the decoded JSON (``dict``/``list``) exactly as the API sends it.

The pandas layer (:class:`rebase_grid.pandas_client.RebasePandasClient`)
subclasses this and parses those payloads into DataFrames/Series.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional, Union

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .decorators import DateLike, clean_params, to_iso8601
from .exceptions import (
    AuthenticationError,
    InvalidParameterError,
    NotFoundError,
    RateLimitError,
    RebaseConfigError,
    RebaseHTTPError,
)

# The live API is served under "/api" (the host root is an SPA that returns
# 200/HTML for any path, so it must NOT be used as the base). Note: some newer
# spec routes (/v1/areas, /v1/assets) are not deployed on this server yet and
# currently return 404 — use the /v1/zone/* metadata endpoints instead.
DEFAULT_BASE_URL = "https://grid.rebase.energy/api"
API_KEY_ENV_VAR = "REBASE_API_KEY"

# Statuses worth retrying with backoff (transient server / rate-limit errors).
_RETRY_STATUSES = (429, 500, 502, 503, 504)


class RebaseRawClient:
    """Thin HTTP wrapper over the Rebase Grid API returning raw JSON.

    Parameters
    ----------
    api_key:
        Rebase API token. If omitted, it is read from the ``REBASE_API_KEY``
        environment variable (a local ``.env`` is loaded automatically).
    session:
        Optional pre-configured :class:`requests.Session`. If omitted, one is
        created with sensible retry/backoff defaults.
    base_url:
        API root. Defaults to ``https://grid.rebase.energy/api``.
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Number of automatic retries for transient errors (429/5xx).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        if api_key is None:
            load_dotenv()
            api_key = os.getenv(API_KEY_ENV_VAR)
        if not api_key:
            raise RebaseConfigError(
                "No API key provided. Pass api_key=... or set the "
                f"{API_KEY_ENV_VAR} environment variable (e.g. in a .env file)."
            )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or self._build_session(max_retries)
        self.session.headers.update(
            {"X-API-Key": self.api_key, "Accept": "application/json"}
        )

    # ------------------------------------------------------------------ #
    # Infrastructure
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=_RETRY_STATUSES,
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """Perform a GET request and return decoded JSON.

        Strips ``None`` params, maps HTTP errors to the client's exception
        hierarchy, and returns the parsed JSON body.
        """
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(
                url, params=clean_params(params or {}), timeout=self.timeout
            )
        except requests.RequestException as exc:  # network-level failure
            raise RebaseHTTPError(f"Request to {url} failed: {exc}") from exc

        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return

        status = response.status_code
        detail = _extract_detail(response)
        message = f"{status} {response.reason} for {response.url}: {detail}"

        if status in (401, 403):
            raise AuthenticationError(message, status, response)
        if status == 404:
            raise NotFoundError(message, status, response)
        if status == 422:
            raise InvalidParameterError(message, status, response)
        if status == 429:
            raise RateLimitError(message, status, response)
        raise RebaseHTTPError(message, status, response)

    def _timeseries_params(
        self,
        start: Optional[DateLike],
        end: Optional[DateLike],
        **extra: Any,
    ) -> dict:
        """Assemble the common ``start``/``end`` (+ extra) query params."""
        return {"start": to_iso8601(start), "end": to_iso8601(end), **extra}

    # ================================================================== #
    # Zones (metadata)
    # ================================================================== #
    def list_zones(self) -> dict:
        """``GET /v1/zone/list`` — list all available zones and their sources.

        Returns ``{"zones": [...]}``; each zone carries ``zone_key``,
        ``zone_name``, ``country``, ``timezone`` and per-datatype ``sources`` /
        ``api_source`` mappings.
        """
        return self._get("/v1/zone/list")

    def get_zone(self, zone_key: str) -> dict:
        """``GET /v1/zone/get/{zone_key}`` — metadata for a single zone."""
        return self._get(f"/v1/zone/get/{zone_key}")

    def get_zone_coverage(self, zone_key: str) -> dict:
        """``GET /v1/zone/{zone_key}/coverage`` — data-availability buckets."""
        return self._get(f"/v1/zone/{zone_key}/coverage")

    def get_zone_sources(self, zone_key: str) -> dict:
        """``GET /v1/zone/{zone_key}/sources`` — sources available for a zone."""
        return self._get(f"/v1/zone/{zone_key}/sources")

    def list_sources(self, zone_key: str) -> dict:
        """``GET /v1/sources`` — ``(source, variable)`` pairs for ``zone_key``."""
        return self._get("/v1/sources", {"zone_key": zone_key})

    # ================================================================== #
    # Timeseries
    # ================================================================== #
    def query_production(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        resolution: Optional[str] = None,
        fuel: Optional[str] = None,
    ) -> dict:
        """``GET /v1/zone/{zone_key}/production`` — generation by fuel (MW).

        ``resolution`` is one of ``native|5M|15M|30M|1H`` (see
        :data:`rebase_grid.mappings.RESOLUTIONS`); ``fuel`` filters to a single
        production mode (default ``all``). Columnar ``data`` has one column per
        fuel present in the window.
        """
        params = self._timeseries_params(
            start, end, source=source, resolution=resolution, fuel=fuel
        )
        return self._get(f"/v1/zone/{zone_key}/production", params)

    def query_price(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> dict:
        """``GET /v1/zone/{zone_key}/price`` — day-ahead spot price.

        Returns the raw price payload including ``currency`` and columnar
        ``data`` (``datetime`` / ``price``). ``start``/``end`` default to the
        last 24 hours; ``source`` defaults to the zone's preferred source.
        """
        params = self._timeseries_params(start, end, source=source)
        return self._get(f"/v1/zone/{zone_key}/price", params)

    def query_consumption(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> dict:
        """``GET /v1/zone/{zone_key}/consumption`` — total system load (MW)."""
        params = self._timeseries_params(start, end, source=source)
        return self._get(f"/v1/zone/{zone_key}/consumption", params)

    def query_storage(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> dict:
        """``GET /v1/zone/{zone_key}/storage`` — storage levels/flows by type."""
        params = self._timeseries_params(start, end, source=source)
        return self._get(f"/v1/zone/{zone_key}/storage", params)

    def query_installed_capacity(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        breakdown: Optional[str] = None,
    ) -> dict:
        """``GET /v1/statistics/installed-capacity/{zone_key}`` — installed
        generation capacity by fuel (MW, annual ``P1Y`` resolution).

        ``start`` defaults to ``2015-01-01`` server-side; ``breakdown`` defaults
        to ``fuel``.
        """
        params = self._timeseries_params(start, end, source=source, breakdown=breakdown)
        return self._get(f"/v1/statistics/installed-capacity/{zone_key}", params)

    def query_installed_capacity_sources(
        self,
        zone_key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
    ) -> dict:
        """``GET /v1/statistics/installed-capacity/{zone_key}/sources`` — the
        installed-capacity series broken out per source."""
        params = self._timeseries_params(start, end)
        return self._get(f"/v1/statistics/installed-capacity/{zone_key}/sources", params)

    def query_grid_installed_capacity(
        self,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
    ) -> dict:
        """``GET /v1/grid/installed-capacity`` — bulk installed capacity across
        all zones (undocumented but live)."""
        params = self._timeseries_params(start, end)
        return self._get("/v1/grid/installed-capacity", params)

    # ================================================================== #
    # Exchange (physical flows, pairs, transfer capacity)
    # ================================================================== #
    def list_exchanges(self) -> dict:
        """``GET /v1/exchange/list`` — all physical-flow pairs (``A->B`` keys)."""
        return self._get("/v1/exchange/list")

    def get_exchange(self, exchange_key: str) -> dict:
        """``GET /v1/exchange/get/{exchange_key}`` — pair metadata."""
        return self._get(f"/v1/exchange/get/{exchange_key}")

    def get_exchange_coverage(self, exchange_key: str) -> dict:
        """``GET /v1/exchange/{exchange_key}/coverage`` — availability buckets."""
        return self._get(f"/v1/exchange/{exchange_key}/coverage")

    def get_exchange_sources(self, exchange_key: str) -> dict:
        """``GET /v1/exchange/{exchange_key}/sources`` — sources for the pair."""
        return self._get(f"/v1/exchange/{exchange_key}/sources")

    def query_exchange_flows(
        self,
        key: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> dict:
        """``GET /v1/exchange/flows/{key}`` — measured physical flow (MW).

        ``key`` may be a single zone (all its neighbours) or a pair like
        ``DE->FR``. Response holds one entry per counterparty under
        ``exchanges``, each with columnar ``data``.
        """
        params = self._timeseries_params(start, end, source=source, resolution=resolution)
        return self._get(f"/v1/exchange/flows/{key}", params)

    def query_transfer_capacity(
        self,
        from_zone: str,
        to_zone: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
    ) -> dict:
        """``GET /v1/exchange/capacity/{from_zone}/{to_zone}`` — NTC / MaxBex."""
        params = self._timeseries_params(start, end)
        return self._get(f"/v1/exchange/capacity/{from_zone}/{to_zone}", params)

    # ================================================================== #
    # Frequency
    # ================================================================== #
    def get_frequency_live(self) -> dict:
        """``GET /v1/frequency/live`` — most recent grid-frequency samples (Hz)."""
        return self._get("/v1/frequency/live")

    # ================================================================== #
    # Geo (GeoJSON)
    # ================================================================== #
    def list_geo_datasets(self) -> dict:
        """``GET /v1/geo`` — registered geo datasets and their versions."""
        return self._get("/v1/geo")

    def get_geo_dataset(self, name: str, version: Optional[str] = None) -> dict:
        """``GET /v1/geo/{name}`` — manifest for a geo dataset.

        ``version`` pins an ISO date (e.g. ``2026-04-11``); omit for latest.
        """
        return self._get(f"/v1/geo/{name}", {"version": version})

    def get_geo_features(
        self,
        name: str,
        country: Optional[str] = None,
        ids: Optional[Union[str, Iterable[str]]] = None,
        version: Optional[str] = None,
    ) -> dict:
        """``GET /v1/geo/{name}/features`` — raw GeoJSON ``FeatureCollection``.

        Filter with ``country`` (matches ``properties.countryKey``) or ``ids``
        (a comma-separated string or an iterable of ids).
        """
        if ids is not None and not isinstance(ids, str):
            ids = ",".join(str(i) for i in ids)
        params = {"country": country, "ids": ids, "version": version}
        return self._get(f"/v1/geo/{name}/features", params)

    def get_geo_feature(self, name: str, feature_id: str) -> dict:
        """``GET /v1/geo/{name}/features/{feature_id}`` — one GeoJSON feature."""
        return self._get(f"/v1/geo/{name}/features/{feature_id}")

    # ================================================================== #
    # Forecast
    # ================================================================== #
    def query_forecast(
        self,
        zone_key: str,
        variable: str,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        model: Optional[str] = None,
    ) -> dict:
        """``GET /v1/zone/{zone_key}/forecast`` — model forecast for a variable.

        ``variable`` is required, one of ``demand|wind|solar`` (see
        :data:`rebase_grid.mappings.FORECAST_VARIABLES`). The server requires
        **timezone-aware** ``start``/``end`` — pass a ``datetime``/``Timestamp``
        (naive values are coerced to UTC) rather than a bare date string. Not
        every zone/variable has a registered model (``404`` if none).
        """
        params = self._timeseries_params(start, end, variable=variable, model=model)
        return self._get(f"/v1/zone/{zone_key}/forecast", params)

    # ================================================================== #
    # Areas (canonical metadata: countries, bidding zones, control areas)
    # ================================================================== #
    def list_areas(
        self,
        area_type: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> dict:
        """``GET /v1/areas`` — countries, bidding zones, and control areas.

        ``area_type`` filters by kind (e.g. ``country``, ``bidding_zone``,
        ``control_area``); ``country_code`` by ISO 3166-1 alpha-2.
        """
        params = {"area_type": area_type, "country_code": country_code}
        return self._get("/v1/areas", params)

    def get_area(self, area_id: str) -> dict:
        """``GET /v1/areas/{area_id}`` — metadata for a single area."""
        return self._get(f"/v1/areas/{area_id}")

    def get_area_coverage(
        self,
        area_id: str,
        resolution: Optional[str] = None,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        provenance: Optional[str] = None,
    ) -> dict:
        """``GET /v1/areas/{area_id}/coverage`` — data-availability buckets."""
        params = self._timeseries_params(
            start, end, resolution=resolution, source=source, provenance=provenance
        )
        return self._get(f"/v1/areas/{area_id}/coverage", params)

    def get_area_sources(self, area_id: str) -> dict:
        """``GET /v1/areas/{area_id}/sources`` — sources available for an area."""
        return self._get(f"/v1/areas/{area_id}/sources")

    def list_area_assets(
        self,
        area_id: str,
        asset_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> dict:
        """``GET /v1/areas/{area_id}/assets`` — assets located in an area."""
        params = {"asset_type": asset_type, "source": source,
                  "limit": limit, "offset": offset}
        return self._get(f"/v1/areas/{area_id}/assets", params)

    # ================================================================== #
    # Assets (physical infrastructure with GeoJSON geometry; paginated)
    # ================================================================== #
    def list_assets(
        self,
        asset_type: Optional[str] = None,
        area_id: Optional[str] = None,
        country_code: Optional[str] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> dict:
        """``GET /v1/assets`` — physical assets (default 1000/page).

        Paginated: the response carries ``total``, ``limit``, and ``offset``.
        """
        params = {
            "asset_type": asset_type, "area_id": area_id,
            "country_code": country_code, "source": source,
            "limit": limit, "offset": offset,
        }
        return self._get("/v1/assets", params)

    def get_asset(self, asset_id: str) -> dict:
        """``GET /v1/assets/{asset_id}`` — one asset with GeoJSON geometry."""
        return self._get(f"/v1/assets/{asset_id}")

    # ================================================================== #
    # Statistics (period-aggregate datasets; resolution monthly|yearly)
    # ================================================================== #
    def query_carbon_intensity(
        self,
        zone_key: str,
        resolution: str = "monthly",
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> dict:
        """``GET /v1/statistics/carbon-intensity/{zone_key}`` — gCO2eq/kWh.

        ``resolution`` is required by the API: ``monthly`` or ``yearly``.
        """
        params = self._timeseries_params(start, end, resolution=resolution, source=source)
        return self._get(f"/v1/statistics/carbon-intensity/{zone_key}", params)

    def query_electricity_demand(
        self,
        zone_key: str,
        resolution: str = "monthly",
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
    ) -> dict:
        """``GET /v1/statistics/electricity-demand/{zone_key}`` — period demand.

        ``resolution``: ``monthly`` or ``yearly`` (required by the API).
        """
        params = self._timeseries_params(start, end, resolution=resolution, source=source)
        return self._get(f"/v1/statistics/electricity-demand/{zone_key}", params)

    def query_electricity_generation(
        self,
        zone_key: str,
        resolution: str = "monthly",
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        series: Optional[str] = None,
    ) -> dict:
        """``GET /v1/statistics/electricity-generation/{zone_key}`` — period generation.

        ``resolution``: ``monthly`` or ``yearly`` (required by the API).
        """
        params = self._timeseries_params(
            start, end, resolution=resolution, source=source, series=series
        )
        return self._get(f"/v1/statistics/electricity-generation/{zone_key}", params)

    def query_power_sector_emissions(
        self,
        zone_key: str,
        resolution: str = "monthly",
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        source: Optional[str] = None,
        series: Optional[str] = None,
    ) -> dict:
        """``GET /v1/statistics/power-sector-emissions/{zone_key}`` — period emissions.

        ``resolution``: ``monthly`` or ``yearly`` (required by the API).
        """
        params = self._timeseries_params(
            start, end, resolution=resolution, source=source, series=series
        )
        return self._get(f"/v1/statistics/power-sector-emissions/{zone_key}", params)

    # ------------------------------------------------------------------ #
    # Context-manager support
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "RebaseRawClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _extract_detail(response: requests.Response) -> str:
    """Best-effort extraction of an error message from a response body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)[:500]
