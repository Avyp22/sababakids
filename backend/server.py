from fastapi import FastAPI, APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import time
import asyncio
import math
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx

from mock_data import CITY_COORDS, ACTIVITIES
from events_source import EVENT_SOURCES, SOURCE_NAMES, fetch_many, sources_status

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB is optional: it only stores an anonymous search log.
# Leave MONGO_URL empty to run without a database.
mongo_url = os.environ.get('MONGO_URL', '').strip()
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000) if mongo_url else None
db = client[os.environ.get('DB_NAME', 'sababakids')] if client else None

GOOGLE_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()

app = FastAPI(title="SababaKids API")
api_router = APIRouter(prefix="/api")

# ---------- Helpers ----------

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_open_now(hours):
    """Best-effort open-now for curated free-text hours (Israel time)."""
    if not hours:
        return None
    h = hours.lower()
    if "24" in h:
        return True
    now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    minutes = now.hour * 60 + now.minute
    if "daylight" in h:
        return 6 * 60 <= minutes <= 19 * 60
    m = re.search(r"(\d{1,2}):(\d{2})\s*[-\u2013]\s*(\d{1,2}):(\d{2})", hours)
    if not m:
        return None
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    return start <= minutes <= end


CATEGORY_TO_GOOGLE = {
    "park": ("nearby", ["park"]),
    "playground": ("nearby", ["playground"]),
    "museum": ("nearby", ["museum"]),
    "zoo": ("nearby", ["zoo"]),
    "amusement_park": ("nearby", ["amusement_park"]),
    "aquarium": ("nearby", ["aquarium"]),
    "beach": ("text", "beach"),
    "water_park": ("text", "water park"),
    "indoor_play": ("text", "indoor playground for kids"),
}

# "All" search: 4 Google calls instead of 9, by grouping Nearby types together.
ALL_QUERIES = [
    ("nearby", ["park", "playground"]),
    ("nearby", ["museum", "zoo", "amusement_park", "aquarium", "water_park"]),
    ("text", "beach"),
    ("text", "indoor playground for kids"),
]

GOOGLE_TYPE_TO_CATEGORY = {
    "park": "park", "playground": "playground", "museum": "museum",
    "zoo": "zoo", "amusement_park": "amusement_park", "aquarium": "aquarium",
    "water_park": "water_park", "beach": "beach",
}

# The field mask drives Google's price tier. "rich" (default) keeps rating +
# opening hours; "basic" drops them for a cheaper tier with a larger free quota.
PLACES_DETAIL = os.environ.get("GOOGLE_PLACES_DETAIL", "rich").strip().lower()
BASIC_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.primaryType,places.types,places.photos,places.googleMapsUri"
)
RICH_FIELDS = BASIC_FIELDS + ",places.rating,places.userRatingCount,places.currentOpeningHours"
PLACES_FIELD_MASK = BASIC_FIELDS if PLACES_DETAIL == "basic" else RICH_FIELDS

CACHE_TTL_S = 3600          # identical searches within 1h reuse Google results
PHOTO_CACHE_TTL_S = 86400
_places_cache = {}
_photo_cache = {}
_geocode_cache = {}
PHOTO_NAME_RE = re.compile(r"^places/[A-Za-z0-9_-]+/photos/[A-Za-z0-9_-]+$")
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")


def cache_get(cache, key, ttl):
    hit = cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    return None


def cache_put(cache, key, value, max_items=1000):
    if len(cache) >= max_items:
        cache.pop(next(iter(cache)))
    cache[key] = (time.time(), value)

INDOOR_CATEGORIES = {"museum", "aquarium", "indoor_play"}


# ---------- Models ----------

class SearchRequest(BaseModel):
    location: Optional[str] = None            # city/address text
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: float = Field(default=10, ge=1, le=50)
    category: str = "all"
    ages: List[str] = Field(default_factory=list)     # subset of 0-2,3-5,6-9,10+
    setting: str = "all"                              # all|indoor|outdoor
    price: str = "all"                                # all|free|paid


# ---------- Geocode ----------

async def geocode(req: SearchRequest):
    if req.lat is not None and req.lng is not None:
        return req.lat, req.lng, "Your location"
    text = (req.location or "").strip()
    if not text:
        c = CITY_COORDS["tel aviv"]
        return c[0], c[1], "Tel Aviv"

    # Direct "lat,lng"
    if "," in text:
        parts = text.split(",")
        try:
            return float(parts[0]), float(parts[1]), text
        except ValueError:
            pass

    key = text.lower()
    for city, coords in CITY_COORDS.items():
        if city in key:
            return coords[0], coords[1], text

    cached = cache_get(_geocode_cache, key, 30 * 86400)
    if cached:
        return cached

    if GOOGLE_KEY:
        try:
            async with httpx.AsyncClient(timeout=12) as hc:
                r = await hc.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": text, "region": "il", "key": GOOGLE_KEY},
                )
                data = r.json()
                if data.get("status") == "OK" and data.get("results"):
                    loc = data["results"][0]["geometry"]["location"]
                    result = (loc["lat"], loc["lng"], data["results"][0]["formatted_address"])
                    cache_put(_geocode_cache, key, result)
                    return result
        except Exception as e:
            logger.warning(f"Geocode failed: {e}")

    c = CITY_COORDS["tel aviv"]
    return c[0], c[1], "Tel Aviv"


# ---------- Google Places ----------

def _category_for(p, fallback):
    primary = p.get("primaryType")
    if primary in GOOGLE_TYPE_TO_CATEGORY:
        return GOOGLE_TYPE_TO_CATEGORY[primary]
    for t in p.get("types", []):
        if t in GOOGLE_TYPE_TO_CATEGORY:
            return GOOGLE_TYPE_TO_CATEGORY[t]
    return fallback


async def google_places(hc, mode, value, fallback_cat, lat, lng, radius_m, photo_base):
    headers = {
        "X-Goog-Api-Key": GOOGLE_KEY,
        "Content-Type": "application/json",
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    if mode == "nearby":
        url = "https://places.googleapis.com/v1/places:searchNearby"
        body = {
            "includedTypes": value,
            "maxResultCount": 20,
            "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m}},
        }
    else:
        url = "https://places.googleapis.com/v1/places:searchText"
        body = {
            "textQuery": value,
            "maxResultCount": 20,
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m}},
        }
    cache_key = (url, str(value), round(lat, 2), round(lng, 2), radius_m, PLACES_FIELD_MASK)
    data = cache_get(_places_cache, cache_key, CACHE_TTL_S)
    if data is None:
        try:
            r = await hc.post(url, headers=headers, json=body)
        except httpx.HTTPError as e:
            logger.warning(f"Google Places request failed: {e}")
            raise RuntimeError(f"request failed: {type(e).__name__}")
        if r.is_error:
            logger.warning(f"Google Places error {r.status_code}: {r.text[:200]}")
            try:
                status = r.json().get("error", {}).get("status", "")
            except ValueError:
                status = ""
            raise RuntimeError(f"{r.status_code} {status}".strip())
        data = r.json()
        cache_put(_places_cache, cache_key, data)

    out = []
    for p in data.get("places", []):
        loc = p.get("location", {})
        cat = _category_for(p, fallback_cat)
        photo = None
        if p.get("photos"):
            name = p["photos"][0].get("name")
            if name:
                # Served through our backend: hides the API key and caches the photo URL.
                photo = f"{photo_base}/api/photo/{name}"
        oh = p.get("currentOpeningHours") or {}
        open_now = oh.get("openNow")
        hours_text = "; ".join(oh.get("weekdayDescriptions", [])[:1]) or "See Google Maps for hours"
        out.append({
            "id": p.get("id"),
            "name": p.get("displayName", {}).get("text", "Unnamed place"),
            "category": cat,
            "address": p.get("formattedAddress", ""),
            "city": "",
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "rating": p.get("rating"),
            "reviews": p.get("userRatingCount", 0),
            "image": photo,
            "description": "Live result from Google Places.",
            "ages": ["0-2", "3-5", "6-9", "10+"],
            "setting": "indoor" if cat in INDOOR_CATEGORIES else "outdoor",
            "price": None,
            "hours": hours_text,
            "open_now": open_now,
            "features": [],
            "google_maps_uri": p.get("googleMapsUri"),
            "source": "google",
        })
    return out


# ---------- Routes ----------

@api_router.get("/")
async def root():
    return {"message": "SababaKids API running", "google_enabled": bool(GOOGLE_KEY)}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


@api_router.get("/photo/{name:path}")
async def place_photo(name: str):
    if not GOOGLE_KEY or not PHOTO_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail="Photo not found")
    uri = cache_get(_photo_cache, name, PHOTO_CACHE_TTL_S)
    if uri is None:
        async with httpx.AsyncClient(timeout=10) as hc:
            r = await hc.get(
                f"https://places.googleapis.com/v1/{name}/media",
                params={"maxWidthPx": 600, "skipHttpRedirect": "true", "key": GOOGLE_KEY},
            )
        uri = None if r.is_error else r.json().get("photoUri")
        if not uri:
            logger.warning(f"Google photo error {r.status_code}: {r.text[:200]}")
            raise HTTPException(status_code=404, detail="Photo not found")
        cache_put(_photo_cache, name, uri, max_items=5000)
    return RedirectResponse(uri, status_code=302, headers={"Cache-Control": "public, max-age=86400"})


@api_router.post("/places/search")
async def search_places(req: SearchRequest, request: Request):
    lat, lng, resolved = await geocode(req)
    radius_m = req.radius_km * 1000

    results = []
    google_errors = []
    if GOOGLE_KEY:
        if req.category == "all":
            queries = [(mode, value, "park") for mode, value in ALL_QUERIES]
        else:
            mode, value = CATEGORY_TO_GOOGLE.get(req.category, ("nearby", ["park"]))
            queries = [(mode, value, req.category)]
        photo_base = PUBLIC_URL or str(request.base_url).rstrip("/")
        async with httpx.AsyncClient(timeout=15) as hc:
            batches = await asyncio.gather(*[
                google_places(hc, mode, value, fallback, lat, lng, radius_m, photo_base)
                for mode, value, fallback in queries
            ], return_exceptions=True)
        for batch in batches:
            if isinstance(batch, Exception):
                google_errors.append(str(batch))
            else:
                results.extend(batch)

    # Always include curated Israeli activities (rich fallback + local knowledge)
    for a in ACTIVITIES:
        item = dict(a)
        item["source"] = "curated"
        results.append(item)

    # Distance + filtering
    final = []
    seen = set()
    for a in results:
        if a.get("lat") is None or a.get("lng") is None:
            continue
        dist = haversine_km(lat, lng, a["lat"], a["lng"])
        if dist > req.radius_km:
            continue
        if req.category != "all" and a["category"] != req.category:
            continue
        if req.setting != "all" and a.get("setting") not in (req.setting, None):
            continue
        if req.price != "all":
            if req.price == "free" and a.get("price") != "free":
                continue
            if req.price == "paid" and a.get("price") not in ("paid", None):
                continue
        if req.ages:
            if not set(req.ages) & set(a.get("ages", [])):
                continue
        key = (a.get("name"), round(a["lat"], 4), round(a["lng"], 4))
        if key in seen:
            continue
        seen.add(key)
        item = dict(a)
        item["distance_km"] = round(dist, 1)
        if item.get("open_now") is None:
            item["open_now"] = compute_open_now(item.get("hours"))
        final.append(item)

    final.sort(key=lambda x: x["distance_km"])

    if db is not None:
        try:
            await db.searches.insert_one({
                "location": resolved, "lat": lat, "lng": lng,
                "radius_km": req.radius_km, "category": req.category,
                "count": len(final), "at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass

    return {
        "center": {"lat": lat, "lng": lng, "label": resolved},
        "count": len(final),
        "google_enabled": bool(GOOGLE_KEY),
        "google_errors": sorted(set(google_errors)),
        "activities": final,
    }


@api_router.get("/events")
def get_events(  # sync: FastAPI runs it in a threadpool so blocking scrapes don't stall other requests
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = Query(50, ge=1, le=200),
    family_only: bool = False,
):
    # Municipal feeds are only queried near their city; Leaan covers the whole country.
    keys = []
    for src in EVENT_SOURCES:
        if lat is None or lng is None or haversine_km(lat, lng, *src["center"]) <= src["trigger_radius_km"]:
            keys.append(src["key"])
    keys.append("leaan")
    results = fetch_many(keys)

    out, live_sources, seen = [], [], set()
    for key in keys:
        added = False
        for ev in results.get(key, []):
            item = dict(ev)
            if lat is not None and lng is not None:
                if item.get("lat") is None:
                    continue  # can't place it near the user
                d = haversine_km(lat, lng, item["lat"], item["lng"])
                if d > radius_km:
                    continue
                item["distance_km"] = round(d, 1)
            if family_only and not item.get("family"):
                continue
            dedupe = (item["name"].strip(), item["date"])
            if dedupe in seen:
                continue
            seen.add(dedupe)
            item["weekday"] = datetime.fromisoformat(item["date"]).strftime("%A")
            out.append(item)
            added = True
        if added:
            live_sources.append(SOURCE_NAMES[key])

    out.sort(key=lambda x: (x["date"], x.get("time") or ""))
    return {"count": len(out), "live_sources": live_sources, "events": out}


@api_router.get("/sources")
def get_sources(refresh: bool = False):
    """Health of each event connector (used by the daily monitoring workflow)."""
    return sources_status(refresh=refresh)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    if client:
        client.close()
