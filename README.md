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

All endpoints the live server implements are wired up on both clients:

- **Zones:** `list_zones`, `get_zone`, `get_zone_coverage`, `get_zone_sources`, `list_sources`
- **Areas:** `list_areas`, `get_area`, `get_area_coverage`, `get_area_sources`, `list_area_assets`
- **Assets:** `list_assets`, `get_asset` (paginated — `total`/`limit`/`offset` in `.attrs`)
- **Timeseries:** `query_production`, `query_price`, `query_consumption`, `query_storage`, `query_forecast`
- **Statistics:** `query_installed_capacity`, `query_installed_capacity_sources`, `query_grid_installed_capacity`, `query_carbon_intensity`, `query_electricity_demand`, `query_electricity_generation`, `query_power_sector_emissions`
- **Exchange:** `list_exchanges`, `get_exchange`, `get_exchange_coverage`, `get_exchange_sources`, `query_exchange_flows`, `query_transfer_capacity`
- **Frequency:** `get_frequency_live`
- **Geo:** `list_geo_datasets`, `get_geo_dataset`, `get_geo_features`, `get_geo_feature`

Return-type conventions (pandas client): timeseries → tz-aware
`DatetimeIndex` `DataFrame`; single-value series (`query_price`,
`query_consumption`) → `Series`; collection metadata → `DataFrame`;
single-entity metadata → `Series`; geo feature payloads → raw GeoJSON `dict`.
Top-level metadata (source, currency, units, …) is attached to `.attrs`.

### Base URL and API notes

The live API is served under `https://grid.rebase.energy/api`. The host root is a
single-page app that returns HTML for any path, so it must not be used as the base.

Notes on the current server (API `v0.2.0`), verified live:

- **Statistics resolution** is `monthly` or `yearly` (required), *not* the
  `native/5M/15M/30M/1H` grid used by production/exchange.
- **Installed capacity** is at `/v1/statistics/installed-capacity/{zone_key}`
  (it moved here in a server update — the old `/v1/zone/.../installed-capacity`
  path now 404s). `query_installed_capacity()` targets the current path.
- **Statistics datasets are routed but not yet populated:** the
  `carbon-intensity`, `electricity-demand`, `electricity-generation`, and
  `power-sector-emissions` endpoints return `200` with empty data for every
  zone, so `query_*` on them currently raises `NoMatchingDataError`. They will
  return data automatically once Rebase ingests the Ember statistics.
- **Forecast** needs timezone-aware `start`/`end` and a registered model for the
  zone/variable, else `404`.

## Errors

All errors derive from `rebase_grid.RebaseError`:
`AuthenticationError` (401/403), `NotFoundError` (404),
`InvalidParameterError` (422), `RateLimitError` (429), `NoMatchingDataError`
(empty result), and `RebaseConfigError` (e.g. missing API key).
