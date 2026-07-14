# rebase-grid

![CI](https://github.com/dfc-economics/rebase-py/actions/workflows/ci.yml/badge.svg)

Python client for the [Rebase Grid API](https://grid.rebase.energy) — REST access
to power-system data (production, price, consumption, exchange, frequency,
statistics, geo, assets) from 70+ TSO parsers worldwide.

The design follows [`entsoe-py`](https://github.com/EnergieID/entsoe-py): a thin
**raw client** returning JSON, and a **pandas client** returning
`DataFrame`/`Series`.

## Install (development)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate
pip install -e ".[dev]"
```

## Authentication

The clients read your token from the `REBASE_API_KEY` environment variable. Copy
`.env.example` to `.env` and paste your token:

```
REBASE_API_KEY=your-token-here
```

`.env` is git-ignored. You can also pass it explicitly: `RebasePandasClient(api_key="...")`.

## Usage

```python
from rebase_grid import RebasePandasClient

client = RebasePandasClient()  # reads REBASE_API_KEY from env / .env

# Metadata: one row per zone
zones = client.list_zones()

# Day-ahead price as a tz-aware Series (currency in series.attrs)
price = client.query_price("DE", start="2024-01-01", end="2024-01-02")
print(price.attrs["currency"], price.head())
```

Need the raw JSON instead? Use `RebaseRawClient`, which has the same methods but
returns the decoded payloads untouched.

## Coverage

All 22 endpoints the live server implements are wired up on both clients:

- **Zones:** `list_zones`, `get_zone`, `get_zone_coverage`, `get_zone_sources`, `list_sources`
- **Timeseries:** `query_production`, `query_price`, `query_consumption`, `query_storage`, `query_installed_capacity`, `query_grid_installed_capacity`
- **Exchange:** `list_exchanges`, `get_exchange`, `get_exchange_coverage`, `get_exchange_sources`, `query_exchange_flows`, `query_transfer_capacity`
- **Frequency:** `get_frequency_live`
- **Geo:** `list_geo_datasets`, `get_geo_dataset`, `get_geo_features`, `get_geo_feature`

The 11 documented-but-undeployed methods (`list_areas`, `get_area*`,
`list_assets`, `get_asset`, and the four `query_*` statistics datasets) exist as
stubs that raise `EndpointNotDeployedError` until the server ships them.

Return-type conventions (pandas client): timeseries → tz-aware
`DatetimeIndex` `DataFrame`; single-value series (`query_price`,
`query_consumption`) → `Series`; collection metadata → `DataFrame`;
single-entity metadata → `Series`; geo feature payloads → raw GeoJSON `dict`.
Top-level metadata (source, currency, units, …) is attached to `.attrs`.

### Base URL & docs-vs-server discrepancy

The live API is served under `https://grid.rebase.energy/api`. The host root is a
single-page app that returns HTML for any path, so it must not be used as the base.

The published docs (`/docs`, and the bundled `docs/api-1.json`) describe **32
endpoints**, but the deployed server (`/api/openapi.json`) implements only **22** —
both are labelled `version 0.2.0`. This library targets what is actually live.

**Documented but not deployed (return 404):** the entire *Areas* family
(`/v1/areas*`), *Assets* family (`/v1/assets*`), and *Statistics* family
(`/v1/statistics/*`). Methods for these exist in the client but will raise
`NotFoundError` until the server ships them.

**Deployed but undocumented (work today):** installed capacity lives at
`/v1/zone/{zone_key}/installed-capacity` and `/v1/grid/installed-capacity` — **not**
the documented `/v1/statistics/installed-capacity/{zone_key}` (which 404s). Use
`query_installed_capacity()` / `query_grid_installed_capacity()`.

## Errors

All errors derive from `rebase_grid.RebaseError`:
`AuthenticationError` (401/403), `NotFoundError` (404),
`InvalidParameterError` (422), `RateLimitError` (429), `NoMatchingDataError`
(empty result), and `RebaseConfigError` (e.g. missing API key).
