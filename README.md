# rebase-grid

![CI](https://github.com/dfc-economics/rebase-py/actions/workflows/ci.yml/badge.svg)

Python client for the [Rebase Grid API](https://grid.rebase.energy/docs/v2/guides/introduction/) —
European power-system data (production, consumption, prices, exchanges, capacities,
balancing) from TSOs, exchanges and transparency platforms, with full version history.

The design follows [`entsoe-py`](https://github.com/EnergieID/entsoe-py): a thin
**raw client** returning JSON, and a **pandas client** returning `DataFrame`/`Series`
with tz-aware datetime indexes.

> **Status: in active development.** The Rebase Grid API is itself evolving, and this
> client tracks it - endpoints and response shapes may change as the upstream API
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

## Concepts

- **Entities** are places that hold data - countries, price zones (`IT-NO`, `DE-LU`),
  borders, ... - arranged as a tree.
- **Timeseries** live on an entity and are identified by a dotted name
  (`category.sub_category.definition[.component]`) plus a **provider** (`entsoe`, `terna`, ...).
- Every value carries a `valid_time` (the interval it covers) and a `knowledge_time`
  (when it became known), so you can read a series **as it was known at any past time**.

## Usage

```python
from rebase_grid import RebasePandasClient

client = RebasePandasClient()  # reads REBASE_API_KEY from env / .env

# Discover: entity tree, or search series across all entities
tree = client.get_entity_tree()
found = client.search_timeseries(q="load", entity="IT-NO")

# Describe: units, resolution, extent, latency and coverage per provider
meta = client.get_timeseries_metadata("IT-NO", "consumption.realised_load.total_load")

# Read: a DataFrame indexed by valid_time with value / knowledge_time / annotation
load = client.query_values(
    "IT-NO", "consumption.realised_load.total_load",
    provider="entsoe", start="2026-10-01", end="2026-10-08",
)

# ... or just the values as a Series
load = client.query_series("IT-NO", "consumption.realised_load.total_load",
                           provider="entsoe", start="2026-10-01", end="2026-10-08")
```

### Reading past versions (`as_of`)

```python
# Everything as it was known at an instant (reproduces a past model run)
client.query_values(entity, name, "entsoe", start, end, as_of="2026-10-08T01:30:00Z")

# One snapshot per day, as known at 10:00 - or per native step with "rolling".
# Result has a (as_of, valid_time) MultiIndex; .unstack("as_of") gives a vintage matrix.
snaps = client.query_values(entity, name, "entsoe", start, end, as_of="P1D", at="10:00")
vintages = snaps["value"].unstack("as_of")
```

### Notes

- Timestamps without a UTC offset (including bare dates) are interpreted as UTC.
- Windows above the API's 100,000-point limit are split automatically; `429`/`503`
  responses are retried, honouring `Retry-After`.
- Empty results raise `NoMatchingDataError`.

For raw JSON instead of pandas, use `RebaseRawClient`.

## Methods

| Group | Methods |
|---|---|
| Account | `get_version`, `get_account` |
| Discover | `get_entity_tree`, `get_entity`, `list_entity_timeseries`, `search_timeseries`, `list_plants`* |
| Describe | `get_timeseries_metadata` |
| Read | `query_values`, `query_series` (pandas only) |

\* The plants endpoint is not implemented server-side yet and raises `EndpointNotImplementedError`.

## Errors

All errors derive from `rebase_grid.RebaseError`: `AuthenticationError` (401),
`InvalidParameterError` (400), `NotFoundError` (404), `RateLimitError` (429),
`EndpointNotImplementedError` (501), `ServiceUnavailableError` (503),
`NoMatchingDataError` (empty result), and `RebaseConfigError` (e.g. missing API key).
HTTP errors expose the API's hints as attributes: `.param`, `.closest` (nearest ids on a
404 - handy for typos), `.providers` (valid providers) and `.retry_after`.

## Legacy v1 API

The earlier v1 API (zones, areas, assets, statistics) is still served and remains
available under `rebase_grid.v1`:

```python
from rebase_grid.v1 import RebasePandasClient as RebaseV1
```

## License

MIT
