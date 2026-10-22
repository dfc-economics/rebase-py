"""Offline tests for RebasePandasClient parsing."""

from __future__ import annotations

import pandas as pd
import pytest

from rebase_grid import NoMatchingDataError
from tests.conftest import BASE_URL


def test_list_areas_returns_dataframe(pandas_client, areas_payload, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/areas", json=areas_payload)
    df = pandas_client.list_areas(country_code="DE")
    assert isinstance(df, pd.DataFrame)
    assert list(df["area_id"]) == ["DE", "FR"]


def test_list_assets_paginated_attrs(pandas_client, requests_mock):
    payload = {
        "assets": [{"asset_id": "a1", "asset_type": "power_plant", "name": "X"}],
        "total": 10475, "limit": 1, "offset": 0,
    }
    requests_mock.get(f"{BASE_URL}/v1/assets", json=payload)
    df = pandas_client.list_assets(country_code="DE", limit=1)
    assert df.attrs["total"] == 10475
    assert list(df["asset_id"]) == ["a1"]


def test_list_zones_returns_dataframe(pandas_client, zones_payload, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/zone/list", json=zones_payload)
    df = pandas_client.list_zones()
    assert isinstance(df, pd.DataFrame)
    assert list(df["zone_key"]) == ["DE", "FR"]


def test_query_price_returns_series(pandas_client, price_payload, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/zone/DE/price", json=price_payload)
    s = pandas_client.query_price("DE", start="2024-01-01", end="2024-01-02")
    assert isinstance(s, pd.Series)
    assert s.name == "price"
    assert isinstance(s.index, pd.DatetimeIndex)
    assert s.index.tz is not None  # tz-aware
    assert s.attrs["currency"] == "EUR"
    assert len(s) == 3


def test_query_price_empty_raises(pandas_client, price_payload, requests_mock):
    empty = dict(price_payload, data={"datetime": [], "price": []})
    requests_mock.get(f"{BASE_URL}/v1/zone/DE/price", json=empty)
    with pytest.raises(NoMatchingDataError):
        pandas_client.query_price("DE")


def test_query_production_multi_fuel_dataframe(pandas_client, requests_mock):
    payload = {
        "zone_key": "DE", "source": "entsoe", "resolution": "native",
        "data": {
            "datetime": ["2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+00:00"],
            "solar": [0.0, 0.0], "wind": [120.0, 130.0],
        },
    }
    requests_mock.get(f"{BASE_URL}/v1/zone/DE/production", json=payload)
    df = pandas_client.query_production("DE")
    assert list(df.columns) == ["solar", "wind"]
    assert df.index.tz is not None
    assert df.attrs["source"] == "entsoe"


def test_exchange_flows_multi_counterparty_prefixed(pandas_client, requests_mock):
    payload = {
        "source": "entsoe", "resolution": "native",
        "exchanges": [
            {"zone_key": "FR", "data": {
                "datetime": ["2024-01-01T00:00:00+00:00"], "net_flow": [100.0]}},
            {"zone_key": "PL", "data": {
                "datetime": ["2024-01-01T00:00:00+00:00"], "net_flow": [-50.0]}},
        ],
    }
    requests_mock.get(f"{BASE_URL}/v1/exchange/flows/DE", json=payload)
    df = pandas_client.query_exchange_flows("DE")
    assert list(df.columns) == ["FR:net_flow", "PL:net_flow"]


def test_grid_installed_capacity_long_form(pandas_client, requests_mock):
    payload = {
        "unit": "MW",
        "zones": {
            "DE": {"data": {"datetime": ["2024-01-01T00:00:00+00:00"], "wind": [1.0]}},
            "FR": {"data": {"datetime": ["2024-01-01T00:00:00+00:00"], "wind": [2.0]}},
        },
    }
    requests_mock.get(f"{BASE_URL}/v1/grid/installed-capacity", json=payload)
    df = pandas_client.query_grid_installed_capacity()
    assert set(df["zone_key"]) == {"DE", "FR"}
    assert df.attrs["unit"] == "MW"
