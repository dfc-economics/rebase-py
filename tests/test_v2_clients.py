"""Offline tests for the v2 raw and pandas clients."""

from __future__ import annotations

import pandas as pd
import pytest

from rebase_grid import (
    AuthenticationError,
    EndpointNotImplementedError,
    InvalidParameterError,
    NoMatchingDataError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)
from rebase_grid.decorators import normalize_as_of, to_rfc3339_utc
from tests.conftest import TEST_KEY, V2_BASE_URL

ENTITY = "IT-NO"
NAME = "consumption.realised_load.total_load"
VALUES_URL = f"{V2_BASE_URL}/entities/{ENTITY}/timeseries/{NAME}/values"


def _points(*triples):
    return [
        {"valid_time": vt, "value": v, "knowledge_time": kt, "annotation": None}
        for vt, v, kt in triples
    ]


# --------------------------------------------------------------------------- #
# Time handling
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-10-01", "2026-10-01T00:00:00Z"),  # bare date -> UTC
        ("2026-10-01T10:00:00", "2026-10-01T10:00:00Z"),  # naive -> UTC
        ("2026-10-01T12:00:00+02:00", "2026-10-01T10:00:00Z"),  # offset -> UTC
        (pd.Timestamp("2026-10-01 12:00", tz="Europe/Rome"), "2026-10-01T10:00:00Z"),
        (None, None),
    ],
)
def test_to_rfc3339_utc(value, expected):
    assert to_rfc3339_utc(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("rolling", "rolling"),
        ("PT1H", "PT1H"),
        ("P1D", "P1D"),
        ("PT15M", "PT15M"),
        ("2026-10-01T10:00:00", "2026-10-01T10:00:00Z"),
    ],
)
def test_normalize_as_of(value, expected):
    assert normalize_as_of(value) == expected


# --------------------------------------------------------------------------- #
# Raw client
# --------------------------------------------------------------------------- #
def test_auth_header_and_utc_params(v2_raw, requests_mock):
    m = requests_mock.get(VALUES_URL, json={"points": []})
    v2_raw.query_values(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-02", at="10:00")
    req = m.last_request
    assert req.headers["X-API-Key"] == TEST_KEY
    assert req.qs["start"] == ["2026-10-01t00:00:00z"]
    assert req.qs["provider"] == ["entsoe"]
    assert req.qs["at"] == ["10:00"]
    assert "as_of" not in req.qs  # None params are dropped


def test_path_segments_are_quoted(v2_raw, requests_mock):
    m = requests_mock.get(f"{V2_BASE_URL}/entities/A%3EB", json={"id": "A>B"})
    assert v2_raw.get_entity("A>B")["id"] == "A>B"
    assert m.called


@pytest.mark.parametrize(
    "status,body,exc",
    [
        (401, {"error": "unauthorized", "message": "bad key"}, AuthenticationError),
        (404, {"error": "not_found", "message": "no", "closest": ["IT-NO"]}, NotFoundError),
        (400, {"error": "bad_request", "message": "x", "param": "start"}, InvalidParameterError),
        (429, {"error": "rate_limited", "message": "slow"}, RateLimitError),
        (501, {"error": "not_implemented", "message": "soon"}, EndpointNotImplementedError),
        (503, {"error": "index_warming", "message": "wait"}, ServiceUnavailableError),
    ],
)
def test_v2_error_mapping(v2_raw, requests_mock, status, body, exc):
    requests_mock.get(f"{V2_BASE_URL}/me", status_code=status, json=body)
    with pytest.raises(exc) as info:
        v2_raw.get_account()
    assert info.value.status_code == status


def test_error_carries_param_closest_providers_retry_after(v2_raw, requests_mock):
    requests_mock.get(
        f"{V2_BASE_URL}/entities/IT-NORD",
        status_code=404,
        json={"error": "not_found", "message": "no entity", "closest": ["IT-NO", "IT-CNO"]},
    )
    with pytest.raises(NotFoundError) as info:
        v2_raw.get_entity("IT-NORD")
    assert info.value.closest == ["IT-NO", "IT-CNO"]

    requests_mock.get(
        VALUES_URL,
        status_code=429,
        headers={"Retry-After": "12"},
        json={"error": "rate_limited", "message": "slow"},
    )
    with pytest.raises(RateLimitError) as info:
        v2_raw.query_values(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-02")
    assert info.value.retry_after == 12.0

    requests_mock.get(
        VALUES_URL,
        status_code=400,
        json={"error": "bad_request", "message": "provider", "param": "provider",
              "providers": ["entsoe", "terna"]},
    )
    with pytest.raises(InvalidParameterError) as info:
        v2_raw.query_values(ENTITY, NAME, "nope", "2026-10-01", "2026-10-02")
    assert info.value.param == "provider" and info.value.providers == ["entsoe", "terna"]


def test_iter_search_follows_cursor(v2_raw, requests_mock):
    def page(request, context):
        cursor = request.qs.get("cursor", [None])[0]
        if cursor is None:
            return {"total": 3, "items": [{"name": "a"}, {"name": "b"}], "next": "2"}
        return {"total": 3, "items": [{"name": "c"}], "next": None}

    requests_mock.get(f"{V2_BASE_URL}/timeseries", json=page)
    assert [i["name"] for i in v2_raw.iter_search_timeseries(q="load")] == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# Pandas client
# --------------------------------------------------------------------------- #
def test_entity_tree_flattened(v2_pandas, requests_mock):
    tree = {"entities": [{"id": "Italy", "kind": "country", "timeseries": 87, "children": [
        {"id": "IT-NO", "kind": "price_zone", "timeseries": 89},
        {"id": "IT-SO", "kind": "price_zone", "timeseries": 87},
    ]}]}
    requests_mock.get(f"{V2_BASE_URL}/entities", json=tree)
    df = v2_pandas.get_entity_tree()
    assert list(df["id"]) == ["Italy", "IT-NO", "IT-SO"]
    assert pd.isna(df["parent"].iloc[0]) and list(df["parent"].iloc[1:]) == ["Italy", "Italy"]
    assert list(df["depth"]) == [0, 1, 1]


def test_search_collects_all_pages(v2_pandas, requests_mock):
    def page(request, context):
        if request.qs.get("cursor"):
            return {"total": 2, "items": [{"entity": "B", "name": "y", "provider": "p", "data_type": "actual"}], "next": None}
        return {"total": 2, "items": [{"entity": "A", "name": "x", "provider": "p", "data_type": "forecast"}], "next": "1"}

    requests_mock.get(f"{V2_BASE_URL}/timeseries", json=page)
    df = v2_pandas.search_timeseries(q="x")
    assert list(df["entity"]) == ["A", "B"]


def test_metadata_one_row_per_provider(v2_pandas, requests_mock):
    payload = {
        "entity": {"id": ENTITY}, "name": NAME, "unit": "MW", "data_type": "actual",
        "definition": {"measures": "load"}, "component": None,
        "providers": [{
            "provider": "entsoe", "resolution": "PT15M", "coverage": 1.0,
            "extent": {"first": "2026-09-03T14:00:00Z", "last": "2026-10-22T11:30:00Z"},
            "latency_minutes": {"p05": 48, "p50": 79, "p95": 202},
            "publication_time": "measured",
        }],
    }
    requests_mock.get(f"{V2_BASE_URL}/entities/{ENTITY}/timeseries/{NAME}", json=payload)
    df = v2_pandas.get_timeseries_metadata(ENTITY, NAME)
    assert df.loc[0, "latency_p50"] == 79 and df.loc[0, "resolution"] == "PT15M"
    assert df.attrs["unit"] == "MW"


def test_query_values_flat_frame(v2_pandas, requests_mock):
    payload = {
        "entity": ENTITY, "name": NAME, "provider": "entsoe", "unit": "MW",
        "resolution": "PT15M", "publication_time": "measured", "as_of": None,
        "points": _points(
            ("2026-10-01T00:00:00Z", 100.0, "2026-10-01T01:00:00Z"),
            ("2026-10-01T00:15:00Z", 110.0, "2026-10-01T01:00:00Z"),
        ),
    }
    requests_mock.get(VALUES_URL, json=payload)
    df = v2_pandas.query_values(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-02")
    assert list(df.columns) == ["value", "knowledge_time", "annotation"]
    assert df.index.tz is not None and df.index.name == "valid_time"
    assert df.attrs["unit"] == "MW" and df.attrs["resolution"] == "PT15M"
    s = v2_pandas.query_series(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-02")
    assert s.name == f"entsoe:{NAME}" and s.iloc[1] == 110.0


def test_query_values_empty_raises(v2_pandas, requests_mock):
    requests_mock.get(VALUES_URL, json={"points": []})
    with pytest.raises(NoMatchingDataError):
        v2_pandas.query_values(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-02")


def test_query_values_snapshots_paged_multiindex(v2_pandas, requests_mock):
    def page(request, context):
        if request.qs.get("cursor"):
            return {"snapshots": [{"as_of": "2026-10-01T02:00:00Z", "points": _points(
                ("2026-10-01T00:00:00Z", 103.0, "2026-10-01T01:30:00Z"))}], "next": None}
        return {"snapshots": [{"as_of": "2026-10-01T01:00:00Z", "points": _points(
            ("2026-10-01T00:00:00Z", 100.0, "2026-10-01T00:30:00Z"))}], "next": "1"}

    requests_mock.get(VALUES_URL, json=page)
    df = v2_pandas.query_values(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-02", as_of="PT1H")
    assert df.index.names == ["as_of", "valid_time"]
    vint = df["value"].unstack("as_of")  # vintage matrix: one column per snapshot
    assert vint.shape == (1, 2) and list(vint.iloc[0]) == [100.0, 103.0]


def test_query_values_bisects_when_window_too_large(v2_pandas, requests_mock):
    """A 400 on `end` ("more than 100000 points") triggers an automatic split."""
    calls = []

    def respond(request, context):
        lo = pd.Timestamp(request.qs["start"][0]); hi = pd.Timestamp(request.qs["end"][0])
        calls.append((lo, hi))
        if hi - lo > pd.Timedelta(days=2):
            context.status_code = 400
            return {"error": "bad_request", "param": "end",
                    "message": "the window holds more than 100000 points at this series' resolution"}
        idx = pd.date_range(lo, hi, freq="D", tz="UTC")
        return {"points": _points(*[(t.strftime("%Y-%m-%dT%H:%M:%SZ"), 1.0, "2026-10-09T00:00:00Z") for t in idx])}

    requests_mock.get(VALUES_URL, json=respond)
    df = v2_pandas.query_values(ENTITY, NAME, "entsoe", "2026-10-01", "2026-10-09")
    assert len(calls) > 1
    assert df.index.is_unique and df.index.is_monotonic_increasing
    assert len(df) == 9  # 1..9 Oct inclusive, boundary duplicates removed


def test_other_400_is_not_swallowed(v2_pandas, requests_mock):
    requests_mock.get(VALUES_URL, status_code=400,
                      json={"error": "bad_request", "param": "end", "message": "end is before start"})
    with pytest.raises(InvalidParameterError):
        v2_pandas.query_values(ENTITY, NAME, "entsoe", "2026-10-02", "2026-10-01")
