"""Live event scrapers for Israeli municipal event boards.

Currently supports the Modi'in-Maccabim-Re'ut municipality event board, which
exposes rich server-rendered event cards (title, date/time, geo coordinates,
price, age range, description, ticket link and .ics calendar link).
"""
import re
import time
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MODIIN_URL = "https://www.modiin.muni.il/modiinwebsite/EventBoard.aspx?PageID=439_385"
MODIIN_BASE = "https://www.modiin.muni.il/modiinwebsite/"
MODIIN_CENTER = (31.8969, 35.0104)

LEAAN_URL = "https://www.leaan.co.il/"

# Hebrew city -> (lat, lng) for national aggregator geolocation
HEB_CITY_COORDS = {
    "תל אביב": (32.0853, 34.7818), "תל אביב-יפו": (32.0853, 34.7818),
    "ירושלים": (31.7683, 35.2137), "חיפה": (32.7940, 34.9896),
    "ראשון לציון": (31.9730, 34.7925), "פתח תקווה": (32.0871, 34.8878),
    "אשדוד": (31.8040, 34.6553), "נתניה": (32.3215, 34.8532),
    "באר שבע": (31.2518, 34.7913), "בני ברק": (32.0807, 34.8338),
    "חולון": (32.0117, 34.7745), "רמת גן": (32.0684, 34.8248),
    "אשקלון": (31.6688, 34.5715), "רחובות": (31.8948, 34.8093),
    "בת ים": (32.0171, 34.7457), "כפר סבא": (32.1750, 34.9070),
    "הרצליה": (32.1624, 34.8447), "חדרה": (32.4340, 34.9196),
    "מודיעין": (31.8928, 35.0104), "מודיעין מכבים רעות": (31.8928, 35.0104),
    "רעננה": (32.1848, 34.8713), "גבעתיים": (32.0722, 34.8107),
    "הוד השרון": (32.1591, 34.8885), "קרית אתא": (32.8110, 35.1128),
    "נהריה": (33.0058, 35.0948), "לוד": (31.9514, 34.8953),
    "רמלה": (31.9280, 34.8667), "אילת": (29.5577, 34.9519),
    "עכו": (32.9281, 35.0818), "טבריה": (32.7959, 35.5312),
    "נצרת": (32.6996, 35.3035), "בית שמש": (31.7457, 34.9880),
    "כרמיאל": (32.9186, 35.2952), "עפולה": (32.6078, 35.2897),
    "יבנה": (31.8785, 34.7390), "אור עקיבא": (32.5083, 34.9186),
    "קיסריה": (32.5000, 34.8925), "ראש העין": (32.0956, 34.9566),
    "גני תקווה": (32.0631, 34.8722), "יהוד": (32.0333, 34.8892),
    "גבעת שמואל": (32.0776, 34.8483), "זכרון יעקב": (32.5717, 34.9515),
    "קרית ביאליק": (32.8386, 35.0872), "קרית מוצקין": (32.8397, 35.0759),
    "דימונה": (31.0686, 35.0327), "כפר יונה": (32.3170, 34.9340),
}

# Registered municipal live sources: center used to decide when to pull them.
EVENT_SOURCES = [
    {"key": "modiin", "name": "Modi'in Municipality", "center": MODIIN_CENTER,
     "trigger_radius_km": 35, "url": MODIIN_URL},
]

_CACHE = {}          # key -> (timestamp, [events])
_CACHE_TTL = 1800    # 30 minutes

AGE_BUCKETS = [(0, 2, "0-2"), (3, 5, "3-5"), (6, 9, "6-9"), (10, 99, "10+")]

FAMILY_KEYWORDS = ["ילד", "ילדים", "משפחה", "הצגה", "שעת סיפור", "נוער", "גיל",
                   "לגילאים", "תיאטרון", "בובות", "הפעלה"]


def _map_ages(text):
    """Extract an age range from Hebrew text and map to our buckets."""
    lo = hi = None
    m = re.search(r"(?:מגיל|לגיל|גיל)\s*(\d{1,2})\s*(?:עד|-|–|עד גיל)\s*(\d{1,2})", text)
    if not m:
        m = re.search(r"לגילאי\w*\s*(\d{1,2})\s*[-–]\s*(\d{1,2})", text)
    if not m:
        m = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
    else:
        m2 = re.search(r"(?:מגיל|לגיל|גיל)\s*(\d{1,2})\s*(?:ומעלה|\+)", text)
        if m2:
            lo, hi = int(m2.group(1)), 99
    if lo is None:
        return []
    if lo > hi:
        lo, hi = hi, lo
    return [label for (a, b, label) in AGE_BUCKETS if a <= hi and b >= lo]


def _detect_price(text):
    t = text.replace("\u200f", "")
    if any(k in t for k in ["ללא עלות", "חופשית", "הכניסה חופשית", "כניסה חופשית", "ללא תשלום", "חינם"]):
        return "free"
    if "₪" in t or 'ש"ח' in t or "ש''ח" in t or "שקל" in t:
        return "paid"
    return None


def _detect_category(name, text):
    blob = f"{name} {text}"
    if any(k in blob for k in ["הצגה", "תיאטרון", "שעת סיפור", "בובות"]):
        return "show"
    if any(k in blob for k in ["מסיבה", "מופע", "הופעה", "פסטיבל", "קרנבל"]):
        return "festival"
    if any(k in blob for k in ["סדנה", "סדנת", "חוג", "הרצאה", "מפגש"]):
        return "workshop"
    return "activity"


def _is_family(name, text, ages):
    if ages:
        return True
    blob = f"{name} {text}"
    return any(k in blob for k in FAMILY_KEYWORDS)


def _parse_modiin(html):
    soup = BeautifulSoup(html, "lxml")
    today = datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    events = []
    for card in soup.select("div.events"):
        h2 = card.find("h2")
        if not h2:
            continue
        name = h2.get_text(strip=True)

        time_span = card.select_one(".desc .time")
        time_text = time_span.get_text(" ", strip=True) if time_span else ""
        dm = re.search(r"(\d{2})/(\d{2})/(\d{4})", time_text)
        tm = re.search(r"(\d{1,2}:\d{2})", time_text)
        if not dm:
            continue
        try:
            ev_date = datetime(int(dm.group(3)), int(dm.group(2)), int(dm.group(1))).date()
        except ValueError:
            continue
        if ev_date < today:
            continue

        loc_a = card.select_one(".desc .location a")
        venue = loc_a.get_text(strip=True) if loc_a else ""
        lat = lng = None
        href = (loc_a.get("href") if loc_a else "") or ""
        cm = re.search(r"loc:(-?\d+\.\d+),(-?\d+\.\d+)", href)
        if cm:
            lat, lng = float(cm.group(1)), float(cm.group(2))

        text_div = card.select_one(".text")
        paras, ticket_url = [], None
        if text_div:
            for a in text_div.find_all("a", href=True):
                h = a["href"]
                if h.startswith("http") and "maps.google" not in h and "waze.com" not in h:
                    ticket_url = h
                    break
            for p in text_div.find_all("p"):
                if p.find("a"):
                    continue
                t = p.get_text(" ", strip=True)
                if t:
                    paras.append(t)
        description = "  ".join(paras).strip() or name

        img = card.find("img")
        image = None
        if img and img.get("src"):
            src = img["src"].strip()
            image = src if src.startswith("http") else MODIIN_BASE + src

        ics_a = card.find("a", href=lambda x: x and "GetModiinEventAsIcs" in x)
        ics_url = (MODIIN_BASE + ics_a["href"]) if ics_a and ics_a.get("href") else None
        eid = None
        if ics_a:
            em = re.search(r"Eventid=(\d+)", ics_a["href"])
            eid = em.group(1) if em else None

        full_text = f"{name} {description}"
        ages = _map_ages(full_text)
        events.append({
            "id": f"modiin-{eid or len(events)}",
            "name": name,
            "category": _detect_category(name, description),
            "venue": venue,
            "city": "Modi'in",
            "address": venue,
            "lat": lat, "lng": lng,
            "image": image,
            "time": tm.group(1) if tm else "",
            "date": ev_date.isoformat(),
            "weekday": ev_date.strftime("%A"),
            "price": _detect_price(full_text),
            "ages": ages,
            "family": _is_family(name, description, ages),
            "booking": "Buy tickets" if ticket_url else "See details",
            "description": description[:400],
            "ticket_url": ticket_url,
            "ics_url": ics_url,
            "source": "Modi'in Municipality",
            "rtl": True,
        })
    return events


def fetch_source(key):
    cached = _CACHE.get(key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]
    src = next((s for s in EVENT_SOURCES if s["key"] == key), None)
    if not src:
        return []
    try:
        r = httpx.get(src["url"], timeout=25, headers={"User-Agent": "Mozilla/5.0 (SababaKids)"})
        r.raise_for_status()
        events = _parse_modiin(r.text) if key == "modiin" else []
        _CACHE[key] = (time.time(), events)
        return events
    except Exception as e:
        logger.warning(f"Event source '{key}' fetch failed: {e}")
        return cached[1] if cached else []


LEAAN_KIDS_KW = ["ילד", "ילדים", "סיפור", "הצגה", "מופע ילדים", "מספרי סיפורים",
                 "בובות", "פסטיבל מספרי", "משפחה", "הצגות ילדים"]


def _leaan_category(name, cat_name):
    blob = f"{name} {cat_name}"
    if any(k in blob for k in ["הצגה", "תיאטרון", "מחזמר", "סיפור", "בובות"]):
        return "show"
    if any(k in blob for k in ["פסטיבל", "מופע", "הופעה", "מוזיקה", "קונצרט", "סטנדאפ", "קומדיה"]):
        return "festival"
    if any(k in blob for k in ["סדנה", "סדנת", "הרצאה", "חוג"]):
        return "workshop"
    return "activity"


def fetch_leaan():
    """National ticketing aggregator (leaan.co.il, Next.js embedded JSON)."""
    key = "leaan"
    cached = _CACHE.get(key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]
    try:
        r = httpx.get(LEAAN_URL, timeout=25, headers={"User-Agent": "Mozilla/5.0 (SababaKids)"}, follow_redirects=True)
        r.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
        import json as _json
        state = _json.loads(m.group(1))["props"]["pageProps"]["initialState"]
    except Exception as e:
        logger.warning(f"Leaan fetch/parse failed: {e}")
        return cached[1] if cached else []

    # ids that appear inside the dedicated kids section
    kids_ids = set()
    for grp in (state.get("kidsEvents", {}) or {}).get("data", []):
        for ev in grp.get("events", []):
            if ev.get("id") is not None:
                kids_ids.add(ev["id"])

    now = time.time()
    out = []
    for e in state.get("search", {}).get("events", []):
        start = e.get("event_start")
        if not start or start < now:
            continue
        loc = e.get("location") or {}
        city = (loc.get("city") or "").strip()
        coords = HEB_CITY_COORDS.get(city)
        cat_name = ""
        cats = e.get("categories") or {}
        if isinstance(cats, dict) and cats:
            cat_name = list(cats.values())[0].get("category_name", "")
        name = e.get("name") or e.get("event_name") or ""
        dt = datetime.fromtimestamp(start, ZoneInfo("Asia/Jerusalem"))
        image = None
        gal = e.get("gallery") or {}
        try:
            image = (gal.get("desktop") or {}).get("1") or (gal.get("mobile") or {}).get("1")
        except Exception:
            image = None
        image = image or e.get("vivenu_image") or None
        price_val = e.get("starting_price") or 0
        eid = e.get("id")
        slug = quote((name or "event").replace(" ", "-"), safe="")
        ticket = f"{LEAAN_URL}events/{slug}/{eid}"
        is_kids = eid in kids_ids or any(k in f"{name} {cat_name}" for k in LEAAN_KIDS_KW)
        out.append({
            "id": f"leaan-{eid}",
            "name": name,
            "category": _leaan_category(name, cat_name),
            "subtitle": cat_name,
            "venue": loc.get("name", ""),
            "city": city,
            "address": ", ".join([p for p in [loc.get("name"), loc.get("street"), city] if p]),
            "lat": coords[0] if coords else None,
            "lng": coords[1] if coords else None,
            "image": image,
            "time": dt.strftime("%H:%M"),
            "date": dt.date().isoformat(),
            "weekday": dt.strftime("%A"),
            "price": "paid" if price_val and price_val > 0 else "free",
            "price_text": f"₪{price_val}+" if price_val else None,
            "ages": [],
            "family": is_kids,
            "booking": "Buy tickets",
            "description": (f"{cat_name} · " if cat_name else "") + f"{loc.get('name','')}".strip(" ·"),
            "ticket_url": ticket,
            "ics_url": None,
            "source": "Leaan (national)",
            "rtl": True,
        })
    _CACHE[key] = (time.time(), out)
    return out
