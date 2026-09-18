from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import math
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import httpx

from mock_data import CITY_COORDS, ACTIVITIES, EVENTS
from events_source import EVENT_SOURCES, fetch_source, fetch_leaan

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
    "park": ("nearby", "park"),
    "playground": ("nearby", "playground"),
    "museum": ("nearby", "museum"),
    "zoo": ("nearby", "zoo"),
    "amusement_park": ("nearby", "amusement_park"),
    "aquarium": ("nearby", "aquarium"),
    "beach": ("text", "beach"),
    "water_park": ("text", "water park"),
    "indoor_play": ("text", "indoor playground for kids"),
}

GOOGLE_TYPE_TO_CATEGORY = {
    "park": "park", "playground": "playground", "museum": "museum",
    "zoo": "zoo", "amusement_park": "amusement_park", "aquarium": "aquarium",
}

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
                    return loc["lat"], loc["lng"], data["results"][0]["formatted_address"]
        except Exception as e:
            logger.warning(f"Geocode failed: {e}")

    c = CITY_COORDS["tel aviv"]
    return c[0], c[1], "Tel Aviv"


# ---------- Google Places ----------

async def google_places(category, lat, lng, radius_m):
    mode, value = CATEGORY_TO_GOOGLE.get(category, ("nearby", "park"))
    mask = (
        "places.id,places.displayName,places.formattedAddress,places.location,"
        "places.primaryType,places.types,places.photos,places.rating,"
        "places.userRatingCount,places.googleMapsUri,places.goodForChildren,"
        "places.currentOpeningHours,places.regularOpeningHours"
    )
    headers = {
        "X-Goog-Api-Key": GOOGLE_KEY,
        "Content-Type": "application/json",
        "X-Goog-FieldMask": mask,
    }
    if mode == "nearby":
        url = "https://places.googleapis.com/v1/places:searchNearby"
        body = {
            "includedTypes": [value],
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
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.post(url, headers=headers, json=body)
        if r.is_error:
            logger.warning(f"Google Places error {r.status_code}: {r.text[:200]}")
            return []
        data = r.json()

    out = []
    for p in data.get("places", []):
        loc = p.get("location", {})
        types = p.get("types", [])
        cat = category
        for t in types:
            if t in GOOGLE_TYPE_TO_CATEGORY:
                cat = GOOGLE_TYPE_TO_CATEGORY[t]
                break
        photo = None
        if p.get("photos"):
            name = p["photos"][0].get("name")
            if name:
                photo = f"https://places.googleapis.com/v1/{name}/media?maxWidthPx=800&key={GOOGLE_KEY}"
        oh = p.get("currentOpeningHours") or p.get("regularOpeningHours") or {}
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
            "features": ["good_for_children"] if p.get("goodForChildren") else [],
            "google_maps_uri": p.get("googleMapsUri"),
            "source": "google",
        })
    return out


# ---------- Routes ----------

@api_router.get("/")
async def root():
    return {"message": "SababaKids API running", "google_enabled": bool(GOOGLE_KEY)}


@api_router.post("/places/search")
async def search_places(req: SearchRequest):
    lat, lng, resolved = await geocode(req)
    radius_m = req.radius_km * 1000
    categories = [req.category] if req.category != "all" else list(CATEGORY_TO_GOOGLE.keys())

    results = []
    if GOOGLE_KEY:
        for cat in categories:
            results.extend(await google_places(cat, lat, lng, radius_m))

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
        "activities": final,
    }


@api_router.get("/events")
async def get_events(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = Query(50, ge=1, le=200),
    family_only: bool = False,
):
    out = []
    live_sources = []

    # Pull live municipal event feeds near the search center
    for src in EVENT_SOURCES:
        near = True
        if lat is not None and lng is not None:
            d = haversine_km(lat, lng, src["center"][0], src["center"][1])
            near = d <= src["trigger_radius_km"]
        if near:
            for ev in fetch_source(src["key"]):
                item = dict(ev)
                if lat is not None and lng is not None and item.get("lat") is not None:
                    item["distance_km"] = round(haversine_km(lat, lng, item["lat"], item["lng"]), 1)
                out.append(item)
            live_sources.append(src["name"])

    # National aggregator (covers all major cities incl. Jerusalem/Tel Aviv/Haifa)
    national = fetch_leaan()
    added_national = False
    for ev in national:
        item = dict(ev)
        if lat is not None and lng is not None:
            if item.get("lat") is None:
                continue  # skip events we can't place near the user
            d = haversine_km(lat, lng, item["lat"], item["lng"])
            if d > radius_km:
                continue
            item["distance_km"] = round(d, 1)
        out.append(item)
        added_national = True
    if added_national:
        live_sources.append("Leaan (national)")

    # Curated fallback events (always available across Israel)
    today = datetime.now(timezone.utc).date()
    for e in EVENTS:
        ev = dict(e)
        ev_date = today + timedelta(days=ev.pop("day_offset", 0))
        ev["date"] = ev_date.isoformat()
        ev["weekday"] = ev_date.strftime("%A")
        ev["family"] = True
        ev["source"] = "SababaKids picks"
        if lat is not None and lng is not None and ev.get("lat") is not None:
            d = haversine_km(lat, lng, ev["lat"], ev["lng"])
            if d > radius_km:
                continue
            ev["distance_km"] = round(d, 1)
        out.append(ev)

    if family_only:
        out = [e for e in out if e.get("family", True)]

    out.sort(key=lambda x: x["date"])
    return {"count": len(out), "live_sources": live_sources, "events": out}


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
    client.close()
