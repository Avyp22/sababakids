"""Write event snapshots for sources the Render server cannot reach directly.

Some municipal sites block non-Israeli / datacenter IPs (Holon: Israel only;
Haifa: blocks Render). A GitHub Action (and optionally a computer in Israel)
runs this script and publishes the JSON on the `event-data` branch, which the
backend reads instead of calling those sites.

    python snapshot_events.py --out <dir> haifa holon

A source that fails keeps its previous snapshot file untouched.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import events_source as es


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("sources", nargs="+", choices=sorted(es.FETCHERS))
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ok = 0
    for key in args.sources:
        try:
            events = es.FETCHERS[key]()
        except Exception as e:
            print(f"{key}: FAILED ({type(e).__name__}: {e})")
            continue
        if not events:
            print(f"{key}: 0 events, keeping previous snapshot")
            continue
        payload = {"source": key, "generated_at": datetime.now(es.TZ).isoformat(), "events": events}
        (out / f"{key}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{key}: {len(events)} events")
        ok += 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
