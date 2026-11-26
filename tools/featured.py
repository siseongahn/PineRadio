#!/usr/bin/env python3
"""Featured stations: hand-picked lists shown first for a country.

tools/featured/<country file>.m3u (e.g. south_korea.m3u → data/radio/south_korea.json) lists stations
in display order. Each one is put into the country file with "featured": <1-based rank>, and the page
lists featured stations first, in that order. A station already in the data under the same address
(compared like build_stations.norm_url) is replaced by the featured entry.

Per-entry #EXTINF attributes:
  pine-genre="news_talk"     genre key (default: the replaced entry's genre, else "unclassified");
                             GENRE_OVERRIDES in build_stations.py still applies on top
  pine-language="English"    language (default: the country's largest language)
  tvg-logo="https://…"       logo

build_stations.py runs this after every rebuild. To apply list changes without a rebuild:
  python3 -I tools/featured.py data
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_stations import norm_url, override_genre, parse_m3u  # noqa: E402
from geo_lang import LANGUAGE_CODE  # noqa: E402

FEATURED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "featured")


def _dump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def apply(out, active_counts=None):
    index_path = os.path.join(out, "index.json")
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    radio = index["radio"]
    by_file = {info["file"]: name for name, info in radio["countries"].items()}
    for m3u in sorted(glob.glob(os.path.join(FEATURED_DIR, "*.m3u"))):
        rel = "radio/" + os.path.basename(m3u)[:-4] + ".json"
        country = by_file.get(rel)
        if not country:
            print(f"featured: {os.path.basename(m3u)} has no matching country file {rel}, skipped")
            continue
        path = os.path.join(out, rel)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        picks = [(url, name, attrs) for url, name, attrs in parse_m3u(m3u)]
        keys = {norm_url(url) for url, _, _ in picks}

        # take out earlier featured entries and anything at a featured address, remembering its genre
        old_genre = {}
        old_active = {}
        rows = []  # (language, genre, record)
        for lang, lv in doc["languages"].items():
            for genre, gv in lv["genres"].items():
                for rec in gv["stations"]:
                    key = norm_url(rec["url"])
                    if key in keys:
                        old_genre.setdefault(key, genre)
                        old_active.setdefault(rec["url"], rec.get("active", 0))
                        continue
                    if rec.pop("featured", None) is not None:
                        continue
                    rows.append((lang, genre, rec))

        main_lang = max(doc["languages"].items(), key=lambda kv: kv[1]["count"])[0]
        for rank, (url, name, attrs) in enumerate(picks, 1):
            name = name or url
            genre = attrs.get("pine-genre") or old_genre.get(norm_url(url)) or "unclassified"
            rec = {"name": name, "active": (active_counts or {}).get(url, old_active.get(url, 0)), "url": url}
            if attrs.get("tvg-logo"):
                rec["logo"] = attrs["tvg-logo"]
            rec["featured"] = rank
            rows.append((attrs.get("pine-language") or main_lang, override_genre(country, name, genre), rec))

        tree = {}
        for lang, genre, rec in rows:
            tree.setdefault(lang, {}).setdefault(genre, []).append(rec)
        doc["languages"], doc["count"] = {}, 0
        idx = radio["countries"][country]          # updated in place, keeping its key order
        old_count, idx["count"], idx["languages"] = idx["count"], 0, {}
        for lang in sorted(tree, key=lambda k: -sum(map(len, tree[k].values()))):
            gd = {}
            for g in sorted(tree[lang], key=lambda k: (k == "unclassified", k)):
                recs = sorted(tree[lang][g], key=lambda r: r["name"].lower())
                gd[g] = {"count": len(recs), "stations": recs}
            lcount = sum(v["count"] for v in gd.values())
            doc["languages"][lang] = {"count": lcount, "genres": gd}
            idx["languages"][lang] = {"count": lcount, "genres": {g: v["count"] for g, v in gd.items()}}
            doc["count"] += lcount
        idx["count"] = doc["count"]
        radio["total"] += doc["count"] - old_count
        _dump(doc, path)
        print(f"featured: {country}: {len(picks)} stations")

    codes = radio["language_codes"]
    for lang in sorted({l for c in radio["countries"].values() for l in c["languages"]} - codes.keys()):
        if lang in LANGUAGE_CODE:
            codes[lang] = LANGUAGE_CODE[lang]
    _dump(index, index_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -I tools/featured.py <data dir>")
    apply(sys.argv[1])
