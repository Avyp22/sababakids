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

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MODIIN_URL = "https://www.modiin.muni.il/modiinwebsite/EventBoard.aspx?PageID=439_385"
MODIIN_BASE = "https://www.modiin.muni.il/modiinwebsite/"
MODIIN_CENTER = (31.8969, 35.0104)

# Registered live sources: center used to decide when to pull them.
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
