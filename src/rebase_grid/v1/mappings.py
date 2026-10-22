"""Constants and enumerations from the Rebase Grid API contract.

These mirror the OpenAPI spec (``docs/api-1.json``) and give callers
autocompletion / validation targets without hardcoding strings everywhere.
"""

from __future__ import annotations

# Resolution enum accepted by high-frequency timeseries endpoints
# (production, exchange flows, ...).
RESOLUTIONS = ("native", "5M", "15M", "30M", "1H")

# Resolution enum accepted by the period-aggregate statistics endpoints
# (carbon-intensity, electricity-demand, electricity-generation,
# power-sector-emissions). Distinct from RESOLUTIONS above.
STATISTICS_RESOLUTIONS = ("monthly", "yearly")

# Statistics datasets exposed under /v1/statistics/{dataset}/{zone_key}.
STATISTICS_DATASETS = (
    "installed-capacity",
    "carbon-intensity",
    "electricity-demand",
    "electricity-generation",
    "power-sector-emissions",
)

# Variables accepted by the zone forecast endpoint.
FORECAST_VARIABLES = ("demand", "wind", "solar")

# Geo datasets registered under /v1/geo.
GEO_DATASETS = ("world_zones", "entsoe_cty", "entsoe_bzn", "entsoe_cta")
