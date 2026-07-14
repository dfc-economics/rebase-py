"""Offline tests for RebaseRawClient (HTTP, auth, error mapping)."""

from __future__ import annotations

import pytest

from rebase_grid import (
    AuthenticationError,
    EndpointNotDeployedError,
    InvalidParameterError,
    NotFoundError,
    RebaseConfigError,
    RebaseRawClient,
)
from tests.conftest import BASE_URL, TEST_KEY


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("REBASE_API_KEY", raising=False)
    # Avoid picking up a real key from a local .env during the test.
    monkeypatch.setattr("rebase_grid.raw_client.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RebaseConfigError):
        RebaseRawClient(api_key=None)


def test_list_zones_sends_key(raw_client, zones_payload, requests_mock):
    m = requests_mock.get(f"{BASE_URL}/v1/zone/list", json=zones_payload)
    out = raw_client.list_zones()
    assert out == zones_payload
    assert m.last_request.headers["X-API-Key"] == TEST_KEY


def test_optional_params_dropped(raw_client, price_payload, requests_mock):
    import pandas as pd

    m = requests_mock.get(f"{BASE_URL}/v1/zone/DE/price", json=price_payload)
    # source is None -> must be omitted; datetimes coerced to ISO-8601.
    raw_client.query_price("DE", start=pd.Timestamp("2024-01-01"), end="2024-01-02")
    qs = m.last_request.qs
    assert qs["start"] == ["2024-01-01t00:00:00+00:00"]
    assert qs["end"] == ["2024-01-02"]
    assert "source" not in qs


@pytest.mark.parametrize(
    "status,exc",
    [(401, AuthenticationError), (404, NotFoundError), (422, InvalidParameterError)],
)
def test_error_status_mapping(raw_client, requests_mock, status, exc):
    requests_mock.get(
        f"{BASE_URL}/v1/zone/list", status_code=status, json={"detail": "boom"}
    )
    with pytest.raises(exc):
        raw_client.list_zones()


def test_undeployed_endpoint_raises_without_http(raw_client, requests_mock):
    # Stubs must not hit the network; they raise before any request.
    with pytest.raises(EndpointNotDeployedError):
        raw_client.list_areas(country_code="DE")
    with pytest.raises(EndpointNotDeployedError):
        raw_client.query_carbon_intensity("DE")
    assert requests_mock.call_count == 0
