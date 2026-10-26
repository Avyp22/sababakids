"""Offline unit tests: rate limiting, Google budget, geocoding of unknown places,
price/ages inferred for Google results."""
import asyncio
import os
import sys

import pytest
from fastapi import HTTPException
from starlette.requests import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402


def make_request(headers=None, host="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


# --- client IP ---
def test_client_ip_prefers_cloudflare_header_over_spoofable_xff():
    req = make_request({"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "6.6.6.6, 1.1.1.1"})
    assert server.client_ip(req) == "1.1.1.1"


def test_client_ip_falls_back_to_socket():
    assert server.client_ip(make_request()) == "10.0.0.1"


def test_reporter_hash_ignores_forged_xff_behind_cloudflare():
    a = make_request({"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "6.6.6.1"})
    b = make_request({"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "6.6.6.2"})
    assert server._reporter_hash(a) == server._reporter_hash(b)


# --- rate limiting ---
def test_rate_limiter_blocks_after_limit():
    lim = server.RateLimiter(3, 60)
    assert [lim.allow("ip") for _ in range(4)] == [True, True, True, False]
    assert lim.allow("other-ip")


def test_check_rate_raises_429():
    lim = server.RateLimiter(1, 60)
    req = make_request()
    server.check_rate(lim, req)
    with pytest.raises(HTTPException) as e:
        server.check_rate(lim, req)
    assert e.value.status_code == 429


# --- daily Google budget ---
def test_google_budget_caps_calls(monkeypatch):
    monkeypatch.setattr(server, "GOOGLE_DAILY_LIMIT", 2)
    monkeypatch.setattr(server, "_google_budget", {"day": None, "used": 0})
    assert [server.google_budget_take() for _ in range(3)] == [True, True, False]


# --- geocoding ---
def test_unknown_place_without_google_is_not_found(monkeypatch):
    monkeypatch.setattr(server, "GOOGLE_KEY", "")
    monkeypatch.setattr(server, "db", None)
    req = server.SearchRequest(location="xyzqwerty")
    assert asyncio.run(server.geocode(req)) is None


def test_known_city_still_resolves(monkeypatch):
    monkeypatch.setattr(server, "GOOGLE_KEY", "")
    lat, lng, _ = asyncio.run(server.geocode(server.SearchRequest(location="Haifa")))
    assert abs(lat - 32.794) < 0.01


def test_out_of_range_latlng_text_is_not_used_as_coordinates(monkeypatch):
    monkeypatch.setattr(server, "GOOGLE_KEY", "")
    monkeypatch.setattr(server, "db", None)
    assert asyncio.run(server.geocode(server.SearchRequest(location="999,999"))) is None


# --- price / ages inferred for Google results ---
def _google_result(primary):
    place = {"id": "p1", "displayName": {"text": "Some place"}, "primaryType": primary,
             "types": [primary], "location": {"latitude": 32.08, "longitude": 34.78}}

    async def run():
        server._places_cache.clear()
        key = ("https://places.googleapis.com/v1/places:searchNearby", str([primary]),
               32.08, 34.78, 1000, server.PLACES_FIELD_MASK)
        await server.places_cache.put(key, {"places": [place]})
        return await server.google_places(None, "nearby", [primary], "park", 32.08, 34.78, 1000, "")
    return asyncio.run(run())[0]


@pytest.fixture
def no_db(monkeypatch):
    monkeypatch.setattr(server, "db", None)


def test_google_park_is_free_and_all_ages(no_db):
    p = _google_result("park")
    assert p["price"] == "free"
    assert p["ages"] == ["0-2", "3-5", "6-9", "10+"]


def test_google_playground_is_for_young_kids(no_db):
    p = _google_result("playground")
    assert p["price"] == "free"
    assert "10+" not in p["ages"] and "0-2" in p["ages"]


def test_google_museum_price_unknown_and_not_for_babies(no_db):
    p = _google_result("museum")
    assert p["price"] is None
    assert "0-2" not in p["ages"]


# --- admin key + curated endpoint ---
def test_admin_key_accepted_in_header_only_when_right(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(server, "ADMIN_KEY", "secret")
    monkeypatch.setattr(server, "db", None)
    c = TestClient(server.app)
    assert c.get("/api/reports").status_code == 403
    assert c.get("/api/reports", headers={"X-Admin-Key": "wrong"}).status_code == 403
    r = c.get("/api/reports", headers={"X-Admin-Key": "secret"})
    assert r.status_code == 200 and "flagged" in r.json()


def test_curated_endpoint_lists_curated_places_with_small_images():
    from fastapi.testclient import TestClient
    data = TestClient(server.app).get("/api/curated").json()["activities"]
    assert len(data) > 5
    assert all("w=800" in a["image"] for a in data if a["image"])
