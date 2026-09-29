"""Live event connectors for Israeli municipal event boards + a national aggregator.

Sources (all public, server-rendered pages):
- Modi'in-Maccabim-Re'ut municipality event board (date/time, GPS, price, ages, .ics)
- Holon municipality "Havingfun" events list (dates, venue, category, target audience)
- Haifa municipality city-events page (+ its dedicated "family" category)
- Leaan (leaan.co.il) national ticketing site, Next.js embedded JSON

Each connector returns a list of normalised event dicts. Results are cached 30 min
per source; on a failed fetch the last good result is kept.
"""
import os
import re
import time
import json
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote, urljoin
from concurrent.futures import ThreadPoolExecutor

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Jerusalem")
UA = {"User-Agent": "Mozilla/5.0 (compatible; SababaKids/1.0; +https://sababakids.onrender.com)"}

MODIIN_URL = "https://www.modiin.muni.il/modiinwebsite/EventBoard.aspx?PageID=439_385"
MODIIN_BASE = "https://www.modiin.muni.il/modiinwebsite/"
HOLON_URL = "https://www.holon.muni.il/Havingfun/Pages/AllEvents.aspx"
HOLON_BASE = "https://www.holon.muni.il"
HAIFA_URL = "https://www.haifa.muni.il/culture/city-events/"
HAIFA_FAMILY_URL = "https://www.haifa.muni.il/event_cat/family/"
LEAAN_URL = "https://www.leaan.co.il/"

# Multi-week "events" (permanent exhibitions, monthly community-centre programmes)
# are places rather than outings: skip anything longer than this.
MAX_EVENT_SPAN_DAYS = 45

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
    "קרית גת": (31.6100, 34.7642), "קרית שמונה": (33.2073, 35.5697),
    "צפת": (32.9646, 35.4960), "שוהם": (31.9990, 34.9450),
    "נס ציונה": (31.9293, 34.7987), "אלעד": (32.0520, 34.9510),
    "גבעת ברנר": (31.8636, 34.8030), "פרדס חנה": (32.4740, 34.9700),
    "פרדס חנה כרכור": (32.4740, 34.9700), "גלילות": (32.1450, 34.8080),
    "מעלות תרשיחא": (33.0167, 35.2717), "מעלו תרשיחא": (33.0167, 35.2717),
    "נוף הגליל": (32.7090, 35.3250), "נווה ירק": (32.1560, 34.9360),
    "ראש פינה": (32.9690, 35.5420), "קרית אונו": (32.0630, 34.8550),
    "אריאל": (32.1060, 35.1870), "קיבוץ כנרת": (32.7230, 35.5630),
    "כנרת": (32.7230, 35.5630), "קיבוץ יגור": (32.7430, 35.0770), "יגור": (32.7430, 35.0770),
    "נתיבות": (31.4230, 34.5890), "איירפורט סיטי": (32.0000, 34.8930),
    "יקנעם": (32.6590, 35.1050), "יקנעם עילית": (32.6590, 35.1050),
    "מעלה אדומים": (31.7770, 35.2980), "אופקים": (31.3140, 34.6200),
    "שדרות": (31.5250, 34.5960), "קרית ים": (32.8490, 35.0690),
    "טירת כרמל": (32.7610, 34.9710), "נשר": (32.7720, 35.0400),
    "עתלית": (32.6890, 34.9410), "בנימינה": (32.5210, 34.9450),
    "קרית טבעון": (32.7160, 35.1270), "מגדל העמק": (32.6760, 35.2400),
    "בית שאן": (32.4970, 35.4980), "ערד": (31.2590, 35.2130),
    "מצפה רמון": (30.6100, 34.8010), "קרית מלאכי": (31.7310, 34.7460),
    "גדרה": (31.8130, 34.7780), "מזכרת בתיה": (31.8530, 34.8430),
    "באר יעקב": (31.9420, 34.8350), "אור יהודה": (32.0290, 34.8540),
    "טייבה": (32.2660, 35.0100), "אום אל פחם": (32.5170, 35.1520),
    "כפר קאסם": (32.1140, 34.9770), "סחנין": (32.8640, 35.2980),
    "אשדות יעקב": (32.6600, 35.5800), "עין גב": (32.7820, 35.6400),
}


def city_coords(city):
    """Coordinates for a Hebrew city name, tolerant of spelling variants
    ("קריית"/"קרית", "תל אביב - יפו", "קיבוץ X")."""
    if not city:
        return None
    c = re.sub(r"\s*-\s*", "-", city.strip()).replace("קריית", "קרית").replace("״", '"')
    for cand in (c, c.replace("-", " "), c.split("-")[0].strip(), c.replace("קיבוץ ", "")):
        if cand in HEB_CITY_COORDS:
            return HEB_CITY_COORDS[cand]
    return None

# Registered municipal sources: `center` + `trigger_radius_km` decide when a
# source is queried for a given search location.
EVENT_SOURCES = [
    {"key": "modiin", "name": "Modi'in Municipality", "center": (31.8969, 35.0104), "trigger_radius_km": 35},
    {"key": "holon", "name": "Holon Municipality", "center": (32.0117, 34.7745), "trigger_radius_km": 35},
    {"key": "haifa", "name": "Haifa Municipality", "center": (32.7940, 34.9896), "trigger_radius_km": 40},
]

# Sites that block the Render server's IPs (Holon: Israel-only, Haifa: blocks
# Render). On Render these are read from snapshots that snapshot_events.py
# publishes on the `event-data` branch (GitHub Action / a computer in Israel).
GEO_BLOCKED = {"holon", "haifa"}
SNAPSHOT_BASE = os.environ.get(
    "EVENT_SNAPSHOT_BASE", "https://raw.githubusercontent.com/Avyp22/sababakids/event-data")
SNAPSHOT_MAX_AGE_DAYS = 14
USE_SNAPSHOTS = bool(os.environ.get("RENDER")) or os.environ.get("EVENT_USE_SNAPSHOTS") == "1"

_CACHE = {}          # key -> (timestamp, [events])
_CACHE_TTL = 1800    # 30 minutes
_STATUS = {}         # key -> {"ok": bool, "count": int, "at": iso, "error": str}

AGE_BUCKETS = [(0, 2, "0-2"), (3, 5, "3-5"), (6, 9, "6-9"), (10, 99, "10+")]

# Explicit kids/family signals only. Broad words ("גיל", "סיפור", "הצגה") matched
# adult stand-up, storytelling festivals and lectures.
FAMILY_KEYWORDS = ["ילדים", "לילדים", "הורים וילדים", "משפחה", "משפחות", "משפחתי", "משפחתית",
                   "לכל המשפחה", "שעת סיפור", "תיאטרון בובות", "הצגת ילדים", "הצגה לילדים",
                   "לגיל הרך", "פעוטות", "קטנטנים", "הפעלה לילדים", "יצירה לילדים"]
ADULT_KEYWORDS = ["סטנדאפ", "סטנד אפ", "למבוגרים", "18+", "+18", "מסיבת", "בירה", "יין ",
                  "גמלאים", "אזרחים ותיקים", "ותיקים", "רווקים", "זוגות", "נשים בלבד",
                  "הרצאה", "הרצאות", "לגיל השלישי", "טקס", "אזכרה"]
KID_WORDS = ["ילדים", "לילדים", "פעוטות", "הצגת ילדים", "קטנטנים", "לגיל הרך", "שעת סיפור"]


def _adult_only(name):
    """Adult format in the title, not explicitly aimed at kids ("סטנדאפ לילדים" is fine)."""
    return _has(name, ADULT_KEYWORDS) and not _has(name, KID_WORDS)


def _has(text, words):
    return any(w in text for w in words)


def _map_ages(text):
    """Extract an age range from Hebrew text and map to our buckets."""
    lo = hi = None
    m = re.search(r"(?:מגיל|לגיל|גיל|לגילאי)\s*(\d{1,2})\s*(?:עד|-|–|עד גיל)\s*(\d{1,2})", text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
    else:
        m2 = re.search(r"(?:מגיל|לגיל|לגילאי)\s*(\d{1,2})\s*(?:ומעלה|\+)", text)
        if m2:
            lo, hi = int(m2.group(1)), 99
    if lo is None or hi > 99:
        return []
    if lo > hi:
        lo, hi = hi, lo
    if lo >= 16:  # "from age 18" etc. -> not a kids event
        return []
    return [label for (a, b, label) in AGE_BUCKETS if a <= hi and b >= lo]


def _detect_price(text):
    t = text.replace("‏", "")
    if _has(t, ["ללא עלות", "חופשית", "הכניסה חופשית", "כניסה חופשית", "ללא תשלום", "חינם"]):
        return "free"
    if "₪" in t or 'ש"ח' in t or "ש''ח" in t or "שקל" in t:
        return "paid"
    return None


def _detect_category(text):
    if _has(text, ["הצגה", "הצגות", "תיאטרון", "שעת סיפור", "בובות"]):
        return "show"
    if _has(text, ["פסטיבל", "מופע", "הופעה", "קרנבל", "מסיבה", "חגיגה", "יריד", "קמפינג"]):
        return "festival"
    if _has(text, ["סדנה", "סדנת", "סדנאות", "חוג", "יצירה"]):
        return "workshop"
    return "activity"


def is_family(text, ages=None, audience=None, name=None):
    """Kids/family classification. `audience` is the source's own target-audience
    field when it has one (most reliable); otherwise fall back to keywords."""
    # Adult formats win even when a source tags them "families" (e.g. stand-up),
    # unless the title explicitly targets kids.
    if _has(text, ADULT_KEYWORDS) and not _has(name if name is not None else text, KID_WORDS):
        return False
    if name and _has(name, KID_WORDS):
        return True  # the title itself targets kids, whatever the audience field says
    if audience is not None:
        return _has(audience, ["ילדים", "משפחות", "פעוטות", "הורים"]) and not (
            _has(audience, ["מבוגרים", "ותיקים"]) and not _has(audience, ["ילדים", "פעוטות"]))
    return bool(ages) or _has(text, FAMILY_KEYWORDS)


def _base_event(**kw):
    ev = {
        "id": None, "name": "", "category": "activity", "venue": "", "city": "", "address": "",
        "lat": None, "lng": None, "image": None, "time": "", "date": None, "end_date": None,
        "price": None, "price_text": None, "ages": [], "family": False, "description": "",
        "ticket_url": None, "ics_url": None, "source": "", "rtl": True,
    }
    ev.update(kw)
    return ev


def _clip_dates(start, end, today):
    """Return (display_date, end) or None if the event is over or too long."""
    end = end or start
    if end < today:
        return None
    if (end - start).days > MAX_EVENT_SPAN_DAYS:
        return None
    return max(start, today), end


def _get(url):
    r = httpx.get(url, timeout=25, headers=UA, follow_redirects=True)
    r.raise_for_status()
    return r.text


# ---------- Modi'in ----------

def _parse_modiin(html):
    soup = BeautifulSoup(html, "lxml")
    today = datetime.now(TZ).date()
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
            ev_date = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
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
        events.append(_base_event(
            id=f"modiin-{eid or len(events)}", name=name, category=_detect_category(full_text),
            venue=venue, city="מודיעין", address=venue, lat=lat, lng=lng, image=image,
            time=tm.group(1) if tm else "", date=ev_date.isoformat(),
            price=_detect_price(full_text), ages=ages, family=is_family(full_text, ages, name=name),
            description=description[:400], ticket_url=ticket_url or MODIIN_URL, ics_url=ics_url,
            source="Modi'in Municipality",
        ))
    return events


def fetch_modiin():
    return _parse_modiin(_get(MODIIN_URL))


# ---------- Holon ----------

def _parse_ddmmyy(text):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text or "")
    if not m:
        return None
    y = int(m.group(3))
    y = y + 2000 if y < 100 else y
    try:
        return date(y, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _cell(row, cls):
    td = row.select_one(f"td.{cls}")
    if not td:
        return ""
    for s in td.select(".displayNoneIndent"):
        s.decompose()
    return td.get_text(" ", strip=True)


def _parse_holon(html):
    soup = BeautifulSoup(html, "lxml")
    today = datetime.now(TZ).date()
    center = EVENT_SOURCES[1]["center"]
    events = []
    for row in soup.select("tr.rowMain"):
        name = _cell(row, "name")
        start = _parse_ddmmyy(_cell(row, "orgDate")) or _parse_ddmmyy(_cell(row, "date"))
        end = _parse_ddmmyy(_cell(row, "endDate"))
        if not name or not start:
            continue
        span = _clip_dates(start, end, today)
        if not span:
            continue
        audience = _cell(row, "kahalFilter")
        category_he = _cell(row, "catFilter")
        venue = _cell(row, "placeFilter") or _cell(row, "border-xs")
        tm = re.search(r"\d{1,2}:\d{2}", _cell(row, "orgTime"))

        details = row.find_next_sibling("tr")
        description, image, ticket_url, ics_url = "", None, None, None
        if details:
            text = re.sub(r"\s+", " ", details.get_text(" ", strip=True))
            dm = re.search(r"תיאור\s*(.*?)(?:קרדיט צילום|הוסף ליומן|$)", text)
            description = (dm.group(1) if dm else "").strip()
            # Drop link labels such as "לפרטים נוספים ולרכישת כרטיסים >>" / "... מבית תרבות ודעת >"
            description = re.sub(r"(?:לפרטים נוספים[^>]{0,60})?\s*>+", " ", description)
            description = re.sub(r"\s+", " ", description).strip()
            for img in details.find_all("img", src=True):
                if "/SiteCollectionImages/" not in img["src"]:
                    # Quote the Hebrew file name but keep the "?Height=250" query intact.
                    path, _, query = img["src"].partition("?")
                    image = urljoin(HOLON_BASE, quote(path, safe="/:%")) + (f"?{query}" if query else "")
                    break
            for a in details.find_all("a", href=True):
                h = a["href"]
                if "CreateICSFile" in h and not ics_url:
                    ics_url = urljoin(HOLON_BASE, h)
                elif h.startswith("http") and not ticket_url and not _has(
                        h, ["facebook.com", "twitter.com", "google.com", "holon.muni.il", "whatsapp"]):
                    ticket_url = h
        eid = row.get("itemid") or row.get("itemID") or len(events)
        blob = f"{name} {category_he} {description}"
        ages = _map_ages(blob)
        events.append(_base_event(
            id=f"holon-{eid}", name=name, category=_detect_category(f"{name} {category_he}"),
            venue=venue, city="חולון", address=venue, lat=center[0], lng=center[1], image=image,
            time=tm.group(0) if tm else "", date=span[0].isoformat(),
            end_date=span[1].isoformat() if span[1] != span[0] else None,
            price=_detect_price(blob), ages=ages, family=is_family(blob, ages, audience=audience, name=name),
            description=(description or category_he)[:400],
            ticket_url=ticket_url or f"{HOLON_BASE}/Havingfun/Lists/List/CustomDispForm.aspx?ID={eid}",
            ics_url=ics_url, source="Holon Municipality",
        ))
    return events


def fetch_holon():
    return _parse_holon(_get(HOLON_URL))


# ---------- Haifa ----------

# One entry inside a community-centre page, e.g.
# "יום שני 12.10.2026 בשעה 17:30 | מופע מוסיקלי בוקה בוקה | מתנ"ס רמות ספיר | 20 ₪ <description>"
# A second event on the same day repeats only the time: "בשעה 20:30 | ...".
_HAIFA_HEAD_RE = re.compile(r"(?:(\d{1,2})\.(\d{1,2})\.(\d{4})\s*)?בשעה\s*(\d{1,2}:\d{2})\s*\|")
# Text that ends an entry: next weekday label, recurring activities, month header, footer.
_DAYS = "ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת"
_HAIFA_END_RE = re.compile(
    rf"\s*(?:יום (?:{_DAYS})\s*$|ימי (?:{_DAYS}).*$|חודש [א-ת]+.*$|לפרטים נוספים.*$)")
_PRICE_RE = re.compile(r"^(?:עלות:?\s*)?(\d+\s*₪|ללא עלות|חינם)\s*")


def _haifa_items(html):
    """Listing cards -> dicts (one per card; the same event can appear per date)."""
    soup = BeautifulSoup(html, "lxml")
    items = []
    for item in soup.select("div.place-archive-item"):
        link = item.find("a", href=True)
        title_el = item.select_one(".place-title")
        date_el = item.select_one(".place-phone")
        if not (link and title_el and date_el):
            continue
        date_text = date_el.get_text(" ", strip=True)
        dates = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", date_text)
        start = _parse_ddmmyy(dates[0]) if dates else None
        if not start:
            continue
        tm = re.search(r"\d{1,2}:\d{2}", date_text)
        addr_el = item.select_one(".place-address")
        img = item.select_one("img.wp-post-image")
        items.append({
            "eid": str(item.get("data-id") or link["href"]),
            "url": link["href"],
            "name": title_el.get_text(" ", strip=True),
            "start": start,
            "end": _parse_ddmmyy(dates[1]) if len(dates) > 1 else start,
            "time": tm.group(0) if tm else "",
            "venue": addr_el.get_text(" ", strip=True) if addr_el else "",
            "image": img["src"] if img and img.get("src") else None,
            "free": item.select_one(".is-free-event") is not None,
        })
    return items


def _haifa_sub_events(item, today):
    """Community centres publish one 2-month card whose page lists the real events."""
    soup = BeautifulSoup(_get(item["url"]), "lxml")
    main = soup.select_one("main") or soup.body
    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    cut = text.find("אירועים נוספים")
    text = text[:cut] if cut > 0 else text
    center = EVENT_SOURCES[2]["center"]
    events = []
    heads = list(_HAIFA_HEAD_RE.finditer(text))
    current = None
    for i, m in enumerate(heads):
        if m.group(1):
            try:
                current = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                current = None
                continue
        d = current
        body_end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = _HAIFA_END_RE.sub("", text[m.end():body_end])
        parts = [p.strip() for p in body.split("|")]
        if d is None or d < today or len(parts) < 2 or not parts[0]:
            continue
        name, venue, rest = parts[0], parts[1], " | ".join(parts[2:]).strip()
        if any(e["name"] == name and e["date"] == d.isoformat() and e["time"] == m.group(4) for e in events):
            continue  # some pages list the same entry twice
        pm = _PRICE_RE.match(rest)
        price_raw = pm.group(1) if pm else ""
        description = rest[pm.end():] if pm else rest
        blob = f"{name} {description}"
        ages = _map_ages(blob)
        price = "free" if price_raw in ("ללא עלות", "חינם") else ("paid" if "₪" in price_raw else _detect_price(blob))
        events.append(_base_event(
            id=f"haifa-{item['eid']}-{d.isoformat()}-{m.group(4)}-{i}", name=name,
            category=_detect_category(blob), venue=venue or item["venue"], city="חיפה",
            address=item["venue"], lat=center[0], lng=center[1], image=item["image"],
            time=m.group(4), date=d.isoformat(), price=price,
            price_text=price_raw if "₪" in price_raw else None, ages=ages,
            family=is_family(blob, ages, name=name), description=description[:400],
            ticket_url=item["url"], source="Haifa Municipality",
        ))
    return events


def fetch_haifa():
    today = datetime.now(TZ).date()
    center = EVENT_SOURCES[2]["center"]
    items = _haifa_items(_get(HAIFA_URL))
    family_ids = set()
    try:
        family_items = _haifa_items(_get(HAIFA_FAMILY_URL))
        family_ids = {i["eid"] for i in family_items}
        items += family_items  # the general page doesn't list every kids event
    except Exception as e:
        logger.warning(f"Haifa family page failed: {e}")

    events, seen, long_items = [], set(), {}
    for it in items:
        key = (it["eid"], it["start"], it["time"])
        if key in seen:
            continue
        seen.add(key)
        if (it["end"] - it["start"]).days > MAX_EVENT_SPAN_DAYS:
            long_items[it["eid"]] = it  # community-centre programme: expand below
            continue
        span = _clip_dates(it["start"], it["end"], today)
        if not span:
            continue
        ages = _map_ages(it["name"])
        fam = it["eid"] in family_ids or is_family(it["name"], ages)
        if _adult_only(it["name"]):
            fam = False
        events.append(_base_event(
            id=f"haifa-{it['eid']}-{span[0].isoformat()}-{it['time']}", name=it["name"],
            category=_detect_category(it["name"]), venue=it["venue"], city="חיפה", address=it["venue"],
            lat=center[0], lng=center[1], image=it["image"], time=it["time"],
            date=span[0].isoformat(), end_date=span[1].isoformat() if span[1] != span[0] else None,
            price="free" if it["free"] else None, ages=ages, family=fam,
            description=it["venue"], ticket_url=it["url"], source="Haifa Municipality",
        ))

    def expand(it):
        try:
            return _haifa_sub_events(it, today)
        except Exception as e:
            logger.warning(f"Haifa sub-page failed ({it['name']}): {e}")
            return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        for sub in pool.map(expand, long_items.values()):
            events.extend(sub)
    return events


# ---------- Leaan (national) ----------

LEAAN_KIDS_CATEGORY = "ילדים"


def _leaan_category(name, cat_name):
    blob = f"{name} {cat_name}"
    if _has(blob, ["הצגה", "הצגות", "תיאטרון", "מחזמר", "בובות"]):
        return "show"
    if _has(blob, ["פסטיבל", "מופע", "הופעה", "מוזיקה", "קונצרט", "סטנדאפ", "קומדיה", "קרקס"]):
        return "festival"
    if _has(blob, ["סדנה", "סדנת", "חוג"]):
        return "workshop"
    return "activity"


def fetch_leaan():
    html = _get(LEAAN_URL)
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    state = json.loads(m.group(1))["props"]["pageProps"]["initialState"]

    # ids listed in the site's own kids section
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
        coords = city_coords(city)
        cats = e.get("categories") or {}
        cat_names = [c.get("category_name", "") for c in (cats.values() if isinstance(cats, dict) else cats)]
        cat_name = cat_names[0] if cat_names else ""
        name = e.get("name") or e.get("event_name") or ""
        dt = datetime.fromtimestamp(start, TZ)
        gal = e.get("gallery") or {}
        try:
            image = (gal.get("desktop") or {}).get("1") or (gal.get("mobile") or {}).get("1")
        except Exception:
            image = None
        image = image or e.get("vivenu_image") or None
        price_val = e.get("starting_price") or 0
        eid = e.get("id")
        slug = quote((name or "event").replace(" ", "-"), safe="")
        # The site's category is authoritative; keywords only as a fallback.
        family = (LEAAN_KIDS_CATEGORY in cat_names or eid in kids_ids or _has(name, KID_WORDS)
                  or (not cat_names and is_family(name)))
        if _adult_only(name):
            family = False
        out.append(_base_event(
            id=f"leaan-{eid}", name=name, category=_leaan_category(name, cat_name),
            venue=loc.get("name", ""), city=city,
            address=", ".join([p for p in [loc.get("name"), loc.get("street"), city] if p]),
            lat=coords[0] if coords else None, lng=coords[1] if coords else None,
            image=image, time=dt.strftime("%H:%M"), date=dt.date().isoformat(),
            price="paid" if price_val and price_val > 0 else "free",
            price_text=f"₪{price_val}+" if price_val else None,
            family=family, description=(f"{cat_name} · " if cat_name else "") + (loc.get("name") or ""),
            ticket_url=f"{LEAAN_URL}events/{slug}/{eid}", source="Leaan (national)",
        ))
    return out


# ---------- Registry / cache ----------

FETCHERS = {
    "modiin": fetch_modiin,
    "holon": fetch_holon,
    "haifa": fetch_haifa,
    "leaan": fetch_leaan,
}
SOURCE_NAMES = {s["key"]: s["name"] for s in EVENT_SOURCES}
SOURCE_NAMES["leaan"] = "Leaan (national)"


def fetch_snapshot(key):
    """Events for `key` from the published snapshot, dropping past ones."""
    r = httpx.get(f"{SNAPSHOT_BASE}/{key}.json", timeout=15, headers=UA)
    r.raise_for_status()
    payload = r.json()
    generated = datetime.fromisoformat(payload["generated_at"])
    if datetime.now(TZ) - generated > timedelta(days=SNAPSHOT_MAX_AGE_DAYS):
        raise RuntimeError(f"snapshot too old ({payload['generated_at']})")
    today = datetime.now(TZ).date()
    events = []
    for ev in payload["events"]:
        end = date.fromisoformat(ev.get("end_date") or ev["date"])
        if end < today:
            continue
        if ev["date"] < today.isoformat():
            ev = {**ev, "date": today.isoformat()}  # multi-day event already running
        events.append(ev)
    return events


def fetch_source(key):
    cached = _CACHE.get(key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]
    try:
        use_snapshot = USE_SNAPSHOTS and key in GEO_BLOCKED
        events = fetch_snapshot(key) if use_snapshot else FETCHERS[key]()
        _CACHE[key] = (time.time(), events)
        _STATUS[key] = {"ok": True, "count": len(events), "at": datetime.now(TZ).isoformat(),
                        "via": "snapshot" if use_snapshot else "direct"}
        return events
    except Exception as e:
        logger.warning(f"Event source '{key}' failed: {e}")
        _STATUS[key] = {"ok": False, "count": len(cached[1]) if cached else 0,
                        "at": datetime.now(TZ).isoformat(), "error": f"{type(e).__name__}: {e}"[:200]}
        return cached[1] if cached else []


def fetch_many(keys):
    """Fetch several sources in parallel -> {key: events}."""
    keys = list(keys)
    if not keys:
        return {}
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        return dict(zip(keys, pool.map(fetch_source, keys)))


def sources_status(refresh=False):
    if refresh:
        fetch_many(FETCHERS.keys())
    return {k: {"name": SOURCE_NAMES[k], **_STATUS.get(k, {"ok": None, "count": 0})} for k in FETCHERS}
