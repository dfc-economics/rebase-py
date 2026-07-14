"""Constants and enumerations from the Rebase Grid API contract.

These mirror the OpenAPI spec (``docs/api-1.json``) and give callers
autocompletion / validation targets without hardcoding strings everywhere.
"""

from __future__ import annotations

# Resolution enum accepted by timeseries endpoints (production, exchange, ...).
RESOLUTIONS = ("native", "5M", "15M", "30M", "1H")

# Statistics datasets exposed under /v1/statistics/{dataset}/{zone_key}.
STATISTICS_DATASETS = (
    "installed-capacity",
    "carbon-intensity",
    "electricity-demand",
    "electricity-generation",
    "power-sector-emissions",
)

# Geo datasets registered under /v1/geo.
GEO_DATASETS = ("world_zones", "entsoe_cty", "entsoe_bzn", "entsoe_cta")
