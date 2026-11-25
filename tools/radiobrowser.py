#!/usr/bin/env python3
"""Station logos and Radio Browser ids from https://www.radio-browser.info (public, community-run).

Downloads Radio Browser's station list (~55k stations, ~60 MB) and matches it to data/radio/*.json by
stream address (compared like build_stations.norm_url, on both `url` and `url_resolved`). A match gets:
  "rb": "<stationuuid>"   the page uses it to load live details (homepage, codec, votes, …)
  "logo": "<favicon>"     only when the station has no logo yet

Re-running is safe: earlier "rb" ids are replaced. build_stations.py runs this after every rebuild;
if the download fails the build continues without logos.

usage: python3 -I tools/radiobrowser.py <data dir> [stations.json]
  stations.json  an already downloaded list (…/json/stations?limit=100000&hidebroken=false)
"""
import glob
import gzip
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_stations import norm_url  # noqa: E402

API = "https://all.api.radio-browser.info/json/stations?limit=100000&hidebroken=false"
UA = "PineRadio/1.0"


def download():
    req = urllib.request.Request(API, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=600) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return json.loads(body)


def usable_logo(u):
    u = (u or "").strip()
    return u if u.startswith(("https://", "http://")) and len(u) <= 500 else None


def apply(out, dump=None):
    try:
        if dump:
            with open(dump, encoding="utf-8") as f:
                stations = json.load(f)
        else:
            stations = download()
    except (OSError, ValueError) as e:
        print(f"radiobrowser: station list unavailable ({e}), skipped")
        return
    by_url = {}
    for s in stations:
        for u in (s.get("url"), s.get("url_resolved")):
            key = norm_url(u or "")
            if key:
                by_url.setdefault(key, s)
    matched = logos = 0
    for path in sorted(glob.glob(os.path.join(out, "radio", "*.json"))):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        changed = False
        for lang in doc["languages"].values():
            for genre in lang["genres"].values():
                for rec in genre["stations"]:
                    s = by_url.get(norm_url(rec["url"]))
                    uuid = s and s.get("stationuuid")
                    if rec.get("rb") != uuid:
                        if uuid:
                            rec["rb"] = uuid
                        else:
                            rec.pop("rb", None)
                        changed = True
                    if not uuid:
                        continue
                    matched += 1
                    logo = usable_logo(s.get("favicon"))
                    if logo and not rec.get("logo"):
                        rec["logo"] = logo
                        logos += 1
                        changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"radiobrowser: {len(stations)} listed, {matched} matched, {logos} logos added")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python3 -I tools/radiobrowser.py <data dir> [stations.json]")
    apply(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
