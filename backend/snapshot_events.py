"""Write event snapshots for sources the Render server cannot reach directly,
and geocode event venues.

Some municipal sites block non-Israeli / datacenter IPs (Holon: Israel only;
Haifa: blocks Render). A GitHub Action (and optionally a computer in Israel)
runs this script and publishes the JSON on the `event-data` branch, which the
backend reads instead of calling those sites.

    python snapshot_events.py --out <dir> haifa holon
    python snapshot_events.py --out <dir> haifa holon --geocode --also-geocode leaan modiin

(source names must come before --also-geocode, which takes the rest of the line)

A source that fails keeps its previous snapshot file untouched.

--geocode updates <dir>/geocache.json with venue coordinates from OpenStreetMap
Nominatim (free; usage policy: max 1 request/second, identify the app, cache
results). The backend applies it to every source, so distances use the real
venue instead of the city centre.
"""
import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

import events_source as es

NOMINATIM = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA = {"User-Agent": "SababaKids/1.0 (https://sababakids.onrender.com; family events in Israel)"}
MAX_LOOKUPS_PER_RUN = 300
MISS_RETRY_DAYS = 30
MAX_KM_FROM_CITY = 20


def _km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _candidates(venue, city):
    """Queries from most to least specific: full venue, then its first part."""
    v = venue.strip()
    out = [f"{v}, {city}"] if city and city not in v else [v]
    bare = re.sub(r"\s*\([^)]*\)", "", v).strip()  # "תיאטרון גבעתיים (אולם X)" -> "תיאטרון גבעתיים"
    if bare and bare != v:
        out.append(f"{bare}, {city}" if city and city not in bare else bare)
    for sep in [" - ", " – ", ","]:
        if sep in v:
            head = v.split(sep)[0].strip()
            if len(head) > 3:
                out.append(f"{head}, {city}" if city else head)
    return list(dict.fromkeys(out))


def geocode_events(events, cache, budget):
    """Fill `cache` for each (city, venue) not yet known. Returns lookups used."""
    used = 0
    for ev in events:
        venue, city = (ev.get("venue") or "").strip(), (ev.get("city") or "").strip()
        if not venue or len(venue) < 3:
            continue
        key = es.geo_key(city, venue)
        known = cache.get(key)
        if known and ("lat" in known or time.time() - known.get("miss", 0) < MISS_RETRY_DAYS * 86400):
            continue
        center = es.city_coords(city) or ((ev["lat"], ev["lng"]) if ev.get("lat") else None)
        found = None
        for q in _candidates(venue, city):
            if used >= budget:
                return used
            used += 1
            time.sleep(1.1)  # Nominatim policy: 1 request/second
            try:
                r = httpx.get(NOMINATIM, params={"q": q, "format": "json", "limit": 1, "countrycodes": "il",
                                                 "accept-language": "he"}, headers=NOMINATIM_UA, timeout=20)
                hits = r.json() if r.status_code == 200 else []
            except Exception as e:
                print(f"  geocode error {q}: {e}")
                hits = []
            if hits:
                pos = (float(hits[0]["lat"]), float(hits[0]["lon"]))
                if center is None or _km(pos, center) <= MAX_KM_FROM_CITY:
                    found = pos
                    break
        cache[key] = {"lat": round(found[0], 6), "lng": round(found[1], 6)} if found else {"miss": int(time.time())}
    return used


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--geocode", action="store_true", help="update geocache.json with venue coordinates")
    parser.add_argument("--also-geocode", nargs="*", default=[], choices=sorted(es.FETCHERS),
                        help="sources fetched only to geocode their venues (no snapshot written)")
    parser.add_argument("sources", nargs="*", choices=sorted(es.FETCHERS))
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ok = 0
    to_geocode = []
    status = {}
    for key in args.sources:
        try:
            events = es.FETCHERS[key]()
        except Exception as e:
            print(f"{key}: FAILED ({type(e).__name__}: {e})")
            status[key] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
            continue
        if not events:
            print(f"{key}: 0 events, keeping previous snapshot")
            status[key] = {"ok": False, "error": "0 events"}
            continue
        status[key] = {"ok": True, "count": len(events)}
        payload = {"source": key, "generated_at": datetime.now(es.TZ).isoformat(), "events": events}
        (out / f"{key}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{key}: {len(events)} events")
        to_geocode += events
        ok += 1

    if args.geocode:
        for key in args.also_geocode:
            if key in args.sources:
                continue  # already fetched above: don't hit the site twice
            try:
                to_geocode += es.FETCHERS[key]()
            except Exception as e:
                print(f"{key} (geocode only): FAILED ({e})")
        cache_file = out / "geocache.json"
        cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
        before = sum("lat" in v for v in cache.values())
        used = geocode_events(to_geocode, cache, MAX_LOOKUPS_PER_RUN)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print(f"geocache: {sum('lat' in v for v in cache.values())} venues located "
              f"(+{sum('lat' in v for v in cache.values()) - before}), {used} lookups")
        ok += 1
    # Per-runner run report (GitHub Action vs a computer in Israel), readable on the branch.
    runner = os.environ.get("SNAPSHOT_RUNNER", "local")
    (out / f"status-{runner}.json").write_text(json.dumps(
        {"at": datetime.now(es.TZ).isoformat(), "sources": status}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
