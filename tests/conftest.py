"""Shared pytest fixtures. Tests run fully offline via requests-mock."""

from __future__ import annotations

import pytest

from rebase_grid import RebasePandasClient as V2Pandas
from rebase_grid import RebaseRawClient as V2Raw
from rebase_grid.v1 import RebasePandasClient, RebaseRawClient

BASE_URL = "https://grid.rebase.energy/api"  # v1
V2_BASE_URL = "https://grid-api-ffcps6p2ra-ey.a.run.app/v2"
TEST_KEY = "test-key"


@pytest.fixture
def raw_client() -> RebaseRawClient:
    return RebaseRawClient(api_key=TEST_KEY)


@pytest.fixture
def pandas_client() -> RebasePandasClient:
    return RebasePandasClient(api_key=TEST_KEY)


@pytest.fixture
def areas_payload() -> dict:
    return {
        "areas": [
            {"area_id": "DE", "area_type": "country", "name": "Germany",
             "country_code": "DE", "timezone": "Europe/Berlin"},
            {"area_id": "FR", "area_type": "country", "name": "France",
             "country_code": "FR", "timezone": "Europe/Paris"},
        ]
    }


@pytest.fixture
def zones_payload() -> dict:
    return {
        "zones": [
            {"zone_key": "DE", "zone_name": "Germany", "country": "DE",
             "timezone": "Europe/Berlin", "sources": {}, "api_source": {}},
            {"zone_key": "FR", "zone_name": "France", "country": "FR",
             "timezone": "Europe/Paris", "sources": {}, "api_source": {}},
        ]
    }


@pytest.fixture
def price_payload() -> dict:
    return {
        "zone_key": "DE",
        "source": "entsoe",
        "data_type": "price",
        "currency": "EUR",
        "start": "2024-01-01T00:00:00+00:00",
        "end": "2024-01-01T03:00:00+00:00",
        "data": {
            "datetime": [
                "2024-01-01T00:00:00+00:00",
                "2024-01-01T01:00:00+00:00",
                "2024-01-01T02:00:00+00:00",
            ],
            "price": [50.1, 48.7, 45.0],
        },
        "provenance": {"category": "measured", "kind": "spot"},
    }


# --------------------------------------------------------------------------- #
# API v2
# --------------------------------------------------------------------------- #
@pytest.fixture
def v2_raw() -> V2Raw:
    return V2Raw(api_key=TEST_KEY)


@pytest.fixture
def v2_pandas() -> V2Pandas:
    return V2Pandas(api_key=TEST_KEY)
