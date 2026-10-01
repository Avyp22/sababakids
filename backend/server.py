from fastapi import FastAPI, APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import json
import hashlib
import time
import asyncio
import math
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta
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
    "nature": ("text", "natural spring nature reserve"),
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
    "national_park": "nature", "hiking_area": "nature", "state_park": "nature",
}

# Springs, streams and reserves: Google files most of them as plain "park".
NATURE_NAME_RE = re.compile(
    r"(^|\s)(עין|עיינות|מעיין|מעיינות|נחל|שמורת|בריכת|ברכת)\s|\bsprings?\b|\bnature reserve\b|\bwadi\b|\bstream\b",
    re.IGNORECASE)
NATURE_OVERRIDABLE = {"park", "playground", "beach"}
NATURAL_TYPES = {"park", "natural_feature", "national_park", "state_park", "hiking_area",
                 "tourist_attraction", "campground", "beach"}


def _is_natural(p):
    return p.get("primaryType") in NATURAL_TYPES or bool(set(p.get("types", [])) & (NATURAL_TYPES - {"tourist_attraction"}))

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


class Cache:
    """Memory cache backed by MongoDB (when MONGO_URL is set) so Google results
    survive Render restarts and free-tier sleeps."""

    def __init__(self, name, ttl, store, max_items=1000):
        self.name, self.ttl, self.mem, self.max = name, ttl, store, max_items

    @staticmethod
    def _key(key):
        return key if isinstance(key, str) else json.dumps(key, ensure_ascii=False, default=str)

    async def get(self, key):
        k = self._key(key)
        value = cache_get(self.mem, k, self.ttl)
        if value is not None or db is None:
            return value
        try:
            doc = await db.cache.find_one({"_id": f"{self.name}:{k}"})
        except Exception as e:
            logger.warning(f"Mongo cache read failed: {e}")
            return None
        if doc and time.time() - doc["ts"] < self.ttl:
            cache_put(self.mem, k, doc["v"], self.max)
            return doc["v"]
        return None

    async def put(self, key, value):
        k = self._key(key)
        cache_put(self.mem, k, value, self.max)
        if db is None:
            return
        try:
            await db.cache.update_one(
                {"_id": f"{self.name}:{k}"},
                {"$set": {"v": value, "ts": time.time(),
                          "expires": datetime.now(timezone.utc) + timedelta(seconds=self.ttl)}},
                upsert=True)
        except Exception as e:
            logger.warning(f"Mongo cache write failed: {e}")


places_cache = Cache("places", CACHE_TTL_S, _places_cache)
photo_cache = Cache("photo", PHOTO_CACHE_TTL_S, _photo_cache, max_items=5000)
geocode_cache = Cache("geocode", 30 * 86400, _geocode_cache)

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

    cached = await geocode_cache.get(key)
    if cached:
        return tuple(cached)

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
                    await geocode_cache.put(key, list(result))
                    return result
        except Exception as e:
            logger.warning(f"Geocode failed: {e}")

    c = CITY_COORDS["tel aviv"]
    return c[0], c[1], "Tel Aviv"


# ---------- Google Places ----------

# Google often tags these with secondary types like "park" or "museum"
# (a cemetery with gardens, a synagogue with an exhibit) — not kids outings.
EXCLUDED_TYPES = {
    "cemetery", "funeral_home", "place_of_worship", "synagogue", "church", "mosque",
    "hindu_temple", "hospital", "police", "courthouse", "local_government_office",
}
EXCLUDED_PRIMARY_TYPES = {
    "bar", "night_club", "casino", "liquor_store", "wine_bar", "pub",
    "lodging", "hotel", "motel", "hostel", "apartment_building", "real_estate_agency",
}


# Some places are plain "park" for Google but aren't outings (name/address hints).
EXCLUDED_NAME_WORDS = [
    "בית עלמין", "בית קברות", "בית העלמין", "קברות", "cemetery", "graveyard", "memorial park",
    "בית כנסת", "synagogue", "church", "כנסיה", "mosque", "מסגד",
]
# Misclassified by Google and not caught by the rules above; add a place id
# here when a user reports one.
EXCLUDED_PLACE_IDS = {
    "ChIJ6x8sJ_e7HRURYmDH38A6sIA",  # Mike Brant boulevard, Haifa: inside the Hof HaCarmel cemetery
}


def _is_excluded(p):
    types = set(p.get("types", []))
    if types & EXCLUDED_TYPES or p.get("primaryType") in EXCLUDED_TYPES | EXCLUDED_PRIMARY_TYPES:
        return True
    if p.get("id") in EXCLUDED_PLACE_IDS or p.get("id") in HIDDEN_IDS:
        return True
    text = f"{p.get('displayName', {}).get('text', '')} {p.get('formattedAddress', '')}".lower()
    return any(w in text for w in EXCLUDED_NAME_WORDS)


def _category_for(p, fallback):
    primary = p.get("primaryType")
    name = p.get("displayName", {}).get("text", "")
    if NATURE_NAME_RE.search(f"{name} ") and (primary in NATURE_OVERRIDABLE or primary is None
                                             or primary in ("natural_feature", "tourist_attraction")):
        return "nature"
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
    data = await places_cache.get(cache_key)
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
        await places_cache.put(cache_key, data)

    out = []
    for p in data.get("places", []):
        if _is_excluded(p):
            continue
        loc = p.get("location", {})
        cat = _category_for(p, fallback_cat)
        if cat == "nature" and not _is_natural(p):
            continue  # e.g. a clinic named "Maayan" returned by the spring search
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
async def health(deep: bool = False):
    if not deep:
        return {"status": "ok"}
    # Database check, without leaking the connection string.
    if db is None:
        return {"status": "ok", "db": "not configured"}
    try:
        await db.command("ping")
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        msg = re.sub(r"mongodb(\+srv)?://\S+", "<url>", str(e))
        msg = re.sub(r"[\w.-]+\.mongodb\.net", "<host>", msg)
        return {"status": "ok", "db": f"error: {type(e).__name__}: {msg[:200]}"}


@api_router.get("/photo/{name:path}")
async def place_photo(name: str):
    if not GOOGLE_KEY or not PHOTO_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail="Photo not found")
    uri = await photo_cache.get(name)
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
        await photo_cache.put(name, uri)
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
        elif req.category == "nature":
            # Springs are spread over several Google shapes: named places, "מעיין"
            # results, and plain "parks" called עין/נחל (reclassified by name).
            queries = [("text", "natural spring nature reserve", "nature"),
                       ("text", "מעיין", "nature"),
                       ("nearby", ["park"], "park")]
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
        if a["id"] in HIDDEN_IDS:
            continue
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
            if item["id"] in HIDDEN_IDS:
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


# ---------- Reports ("this place/event is wrong") ----------

REPORT_HIDE_THRESHOLD = 3          # distinct reporters before an item is hidden
ADMIN_KEY = os.environ.get("ADMIN_KEY", "").strip()
HIDDEN_IDS = set()                 # loaded from Mongo; applied to places and events
_reports_mem = []                  # fallback when no database is configured


class ReportRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="place", pattern="^(place|event)$")
    name: str = Field(default="", max_length=200)
    reason: str = Field(default="other", max_length=40)
    comment: str = Field(default="", max_length=500)


def _reporter_hash(request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    return hashlib.sha256(f"{ip.split(',')[0].strip()}|{ADMIN_KEY}".encode()).hexdigest()[:16]


async def load_hidden_ids():
    if db is None:
        return
    try:
        ids = [d["_id"] async for d in db.hidden.find({}, {"_id": 1})]
        HIDDEN_IDS.update(ids)
    except Exception as e:
        logger.warning(f"Loading hidden ids failed: {e}")


@api_router.post("/report")
async def report_item(rep: ReportRequest, request: Request):
    doc = {**rep.model_dump(), "reporter": _reporter_hash(request), "at": datetime.now(timezone.utc).isoformat()}
    if db is None:
        _reports_mem.append(doc)
        del _reports_mem[:-500]
        return {"ok": True, "stored": "memory"}
    try:
        await db.reports.update_one(
            {"item_id": rep.item_id, "reporter": doc["reporter"]}, {"$set": doc}, upsert=True)
        distinct = len(await db.reports.distinct("reporter", {"item_id": rep.item_id}))
        if distinct >= REPORT_HIDE_THRESHOLD:
            await db.hidden.update_one({"_id": rep.item_id},
                                       {"$set": {"name": rep.name, "kind": rep.kind, "auto": True}}, upsert=True)
            HIDDEN_IDS.add(rep.item_id)
    except Exception as e:
        logger.warning(f"Saving report failed: {e}")
        return {"ok": False}
    return {"ok": True, "stored": "db"}


@api_router.get("/reports")
async def list_reports(key: str = ""):
    """Admin view: /api/reports?key=ADMIN_KEY"""
    if not ADMIN_KEY or key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    if db is None:
        return {"reports": _reports_mem[-200:], "hidden": sorted(HIDDEN_IDS)}
    reports = [{k: v for k, v in d.items() if k != "_id"}
               async for d in db.reports.find().sort("at", -1).limit(300)]
    return {"reports": reports, "hidden": sorted(HIDDEN_IDS)}


@api_router.post("/hide")
async def hide_item(item_id: str, key: str = "", unhide: bool = False):
    """Admin: hide/unhide an item right away. /api/hide?item_id=...&key=ADMIN_KEY"""
    if not ADMIN_KEY or key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    if unhide:
        HIDDEN_IDS.discard(item_id)
        if db is not None:
            await db.hidden.delete_one({"_id": item_id})
    else:
        HIDDEN_IDS.add(item_id)
        if db is not None:
            await db.hidden.update_one({"_id": item_id}, {"$set": {"auto": False}}, upsert=True)
    return {"ok": True, "hidden": not unhide}


app.include_router(api_router)


@app.on_event("startup")
async def startup():
    if db is None:
        return
    try:
        await db.cache.create_index("expires", expireAfterSeconds=0)
        await db.reports.create_index([("item_id", 1), ("reporter", 1)], unique=True)
    except Exception as e:
        logger.warning(f"Mongo index setup failed: {e}")
    await load_hidden_ids()

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
