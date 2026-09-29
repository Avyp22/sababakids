"""Backend API tests for SababaKids."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Root ---
def test_root(client):
    r = client.get(f"{API}/")
    assert r.status_code == 200
    data = r.json()
    assert "google_enabled" in data
    if not data["google_enabled"]:
        pytest.skip("GOOGLE_MAPS_API_KEY not configured")
    assert "running" in data.get("message", "").lower()


# --- /places/search ---
def test_search_tel_aviv_default(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 15, "category": "all"})
    assert r.status_code == 200
    data = r.json()
    assert data["center"]["label"].lower().startswith("tel aviv") or "tel aviv" in data["center"]["label"].lower()
    # Center should resolve to Tel Aviv coords ~32.08,34.78
    assert abs(data["center"]["lat"] - 32.0853) < 0.01
    assert len(data["activities"]) > 0
    dists = [a["distance_km"] for a in data["activities"]]
    assert dists == sorted(dists), "activities must be sorted by distance ascending"
    for a in data["activities"]:
        assert a["distance_km"] <= 15


def test_search_category_zoo(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "category": "zoo"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    for a in data["activities"]:
        assert a["category"] == "zoo"


def test_search_setting_indoor(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "setting": "indoor"})
    assert r.status_code == 200
    for a in r.json()["activities"]:
        assert a["setting"] == "indoor"


def test_search_setting_outdoor(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "setting": "outdoor"})
    for a in r.json()["activities"]:
        assert a["setting"] == "outdoor"


def test_search_price_free(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "price": "free"})
    for a in r.json()["activities"]:
        assert a["price"] == "free"


def test_search_price_paid(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "price": "paid"})
    for a in r.json()["activities"]:
        assert a["price"] in ("paid", None)


def test_search_ages_filter(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "ages": ["0-2"]})
    data = r.json()
    assert data["count"] > 0
    for a in data["activities"]:
        assert "0-2" in a["ages"]


def test_search_by_latlng_jerusalem(client):
    r = client.post(f"{API}/places/search", json={"lat": 31.7683, "lng": 35.2137, "radius_km": 20})
    assert r.status_code == 200
    data = r.json()
    assert abs(data["center"]["lat"] - 31.7683) < 0.0001
    assert abs(data["center"]["lng"] - 35.2137) < 0.0001
    assert data["count"] > 0
    # should include jerusalem-area activities
    names = [a["name"] for a in data["activities"]]
    assert any("Jerusalem" in a.get("city", "") for a in data["activities"]), f"Expected Jerusalem activities in {names}"


def test_search_radius_filtering(client):
    small = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 2, "category": "all"}).json()
    big = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 50, "category": "all"}).json()
    assert small["count"] < big["count"]


# --- /events ---
def test_events(client):
    r = client.get(f"{API}/events", params={"lat": 32.08, "lng": 34.78, "radius_km": 200})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    from datetime import date
    today = date.today()
    for e in data["events"]:
        assert "date" in e
        assert "weekday" in e
        assert "distance_km" in e
        assert date.fromisoformat(e["date"]) >= today
    dates = [e["date"] for e in data["events"]]
    assert dates == sorted(dates)


def test_events_no_coords(client):
    r = client.get(f"{API}/events")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
