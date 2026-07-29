# rebase-grid

![CI](https://github.com/dfc-economics/rebase-py/actions/workflows/ci.yml/badge.svg)

Python client for the [Rebase Grid API](https://grid.rebase.energy) - REST access to
power-system data (production, price, consumption, exchange, frequency, statistics,
geo, and assets) sourced from TSOs and parsers worldwide.

The design follows [`entsoe-py`](https://github.com/EnergieID/entsoe-py): a thin
**raw client** returning JSON, and a **pandas client** returning `DataFrame`/`Series`
with tz-aware datetime indexes.

> **Status: in active development.** The Rebase Grid API is itself evolving, and this
> client tracks it — endpoints and response shapes may change as the upstream API
> does. Pin a version if you need stability.

## Install

```bash
pip install "git+https://github.com/dfc-economics/rebase-py.git"
```

For local development:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate
pip install -e ".[dev]"
```

## Authentication

The clients read your token from the `REBASE_API_KEY` environment variable. Copy
`.env.example` to `.env` and add your token (`.env` is git-ignored):

```
REBASE_API_KEY=your-token-here
```

You can also pass it explicitly: `RebasePandasClient(api_key="...")`.

## Usage

```python
from rebase_grid import RebasePandasClient

client = RebasePandasClient()  # reads REBASE_API_KEY from env / .env

# Metadata: one row per zone
zones = client.list_zones()

# Day-ahead price as a tz-aware Series (currency in .attrs)
price = client.query_price("DE", start="2024-01-01", end="2024-01-02")
print(price.attrs["currency"], price.head())

# Generation by fuel as a DataFrame (one column per fuel)
production = client.query_production("DE", start="2024-01-01", end="2024-01-02")
```

For raw JSON instead of pandas, use `RebaseRawClient`.

## Available methods

- **Zones:** `list_zones`, `get_zone`, `get_zone_coverage`, `get_zone_sources`, `list_sources`
- **Areas:** `list_areas`, `get_area`, `get_area_coverage`, `get_area_sources`, `list_area_assets`
- **Assets:** `list_assets`, `get_asset` (paginated — `total`/`limit`/`offset` in `.attrs`)
- **Timeseries:** `query_production`, `query_price`, `query_consumption`, `query_storage`, `query_forecast`
- **Statistics:** `query_installed_capacity`, `query_installed_capacity_sources`, `query_grid_installed_capacity`, `query_carbon_intensity`, `query_electricity_demand`, `query_electricity_generation`, `query_power_sector_emissions`
- **Exchange:** `list_exchanges`, `get_exchange`, `get_exchange_coverage`, `get_exchange_sources`, `query_exchange_flows`, `query_transfer_capacity`
- **Frequency:** `get_frequency_live`
- **Geo:** `list_geo_datasets`, `get_geo_dataset`, `get_geo_features`, `get_geo_feature`

## Errors

All errors derive from `rebase_grid.RebaseError`: `AuthenticationError` (401/403),
`NotFoundError` (404), `InvalidParameterError` (422), `RateLimitError` (429),
`NoMatchingDataError` (empty result), and `RebaseConfigError` (e.g. missing API key).

## License

MIT
