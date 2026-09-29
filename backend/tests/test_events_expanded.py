"""Backend tests for /api/events coverage (national Leaan + Modi'in, Holon, Haifa municipalities)."""
import os
from datetime import date

import pytest
import requests
from dotenv import load_dotenv

load_dotenv('/app/frontend/.env')
BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


REQUIRED_KEYS = {"name", "date", "city", "source"}


def _validate_event_shape(e):
    for k in REQUIRED_KEYS:
        assert k in e, f"missing {k} in event {e.get('name')}"
    # date is ISO and >= today
    d = date.fromisoformat(e["date"])
    assert d >= date.today(), f"event {e['name']} has past date {e['date']}"


# --- Tel Aviv: mixed sources ---
def test_events_tel_aviv_all(client):
    r = client.get(f"{API}/events", params={"lat": 32.0853, "lng": 34.7818,
                                            "radius_km": 40, "family_only": "false"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    sources = set(e["source"] for e in data["events"])
    assert "Leaan (national)" in data["live_sources"], f"live_sources={data['live_sources']}"
    # live_sources only lists sources that contributed events within the radius.
    # Modi'in (~28km) and Holon (~8km) are both within 40km of Tel Aviv.
    assert "Modi'in Municipality" in data["live_sources"], f"live_sources={data['live_sources']}"
    assert "Holon Municipality" in data["live_sources"], f"live_sources={data['live_sources']}"
    # dates sorted ascending
    dates = [e["date"] for e in data["events"]]
    assert dates == sorted(dates)
    # at least one leaan ticketed event with ticket_url
    leaan = [e for e in data["events"] if e["source"] == "Leaan (national)"]
    assert leaan, "expected some Leaan events near Tel Aviv"
    for e in leaan[:5]:
        assert e.get("ticket_url"), f"leaan event missing ticket_url: {e['name']}"
    for e in data["events"]:
        _validate_event_shape(e)


# --- Jerusalem ---
def test_events_jerusalem_national(client):
    r = client.get(f"{API}/events", params={"lat": 31.7683, "lng": 35.2137,
                                            "radius_km": 40, "family_only": "false"})
    assert r.status_code == 200
    data = r.json()
    leaan = [e for e in data["events"] if e["source"] == "Leaan (national)"]
    assert leaan, "expected Leaan events near Jerusalem"
    # At least one leaan event should actually be in Jerusalem
    assert any("ירושלים" in (e.get("city", "") + " " + e.get("address", "")) for e in leaan), \
        "expected at least one Leaan event with Jerusalem city"


# --- Haifa ---
def test_events_haifa_national(client):
    r = client.get(f"{API}/events", params={"lat": 32.7940, "lng": 34.9896,
                                            "radius_km": 30, "family_only": "false"})
    assert r.status_code == 200
    data = r.json()
    leaan = [e for e in data["events"] if e["source"] == "Leaan (national)"]
    assert leaan, "expected Leaan events near Haifa"


# --- family_only reduces the list ---
def test_events_family_only_filter(client):
    params = {"lat": 32.0853, "lng": 34.7818, "radius_km": 30}
    all_r = client.get(f"{API}/events", params={**params, "family_only": "false"}).json()
    fam_r = client.get(f"{API}/events", params={**params, "family_only": "true"}).json()
    assert fam_r["count"] <= all_r["count"]
    assert fam_r["count"] > 0
    for e in fam_r["events"]:
        assert e.get("family") is True, f"non-family event leaked: {e['name']}"


# --- Distance filtering ---
def test_events_distance_filter_small_radius(client):
    small = client.get(f"{API}/events", params={"lat": 32.0853, "lng": 34.7818,
                                                "radius_km": 3, "family_only": "false"}).json()
    big = client.get(f"{API}/events", params={"lat": 32.0853, "lng": 34.7818,
                                              "radius_km": 60, "family_only": "false"}).json()
    assert small["count"] <= big["count"]
    for e in small["events"]:
        if e.get("distance_km") is not None:
            assert e["distance_km"] <= 3 + 0.1


# --- Regression: /places/search still returns Google-live or curated near Tel Aviv ---
def test_places_regression(client):
    r = client.post(f"{API}/places/search", json={"location": "Tel Aviv", "radius_km": 15, "category": "all"})
    assert r.status_code == 200
    d = r.json()
    assert "google_enabled" in d
    assert d["count"] > 0


# --- Haifa municipality + family classification ---
def test_events_haifa_municipal(client):
    r = client.get(f"{API}/events", params={"lat": 32.794, "lng": 34.9896, "radius_km": 15, "family_only": "false"})
    assert r.status_code == 200
    data = r.json()
    assert "Haifa Municipality" in data["live_sources"], f"live_sources={data['live_sources']}"


def test_family_only_excludes_standup(client):
    r = client.get(f"{API}/events", params={"family_only": "true"})
    for e in r.json()["events"]:
        assert "סטנדאפ" not in e["name"] or "ילדים" in e["name"], f"adult event leaked: {e['name']}"


def test_sources_status(client):
    r = client.get(f"{API}/sources")
    assert r.status_code == 200
    data = r.json()
    assert {"modiin", "holon", "haifa", "leaan"} <= set(data)
