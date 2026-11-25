#!/usr/bin/env python3
"""m3u 플레이리스트 → JSON 변환 (라디오: 국가 > 언어 > 장르).

usage: python3 -I build_stations.py <radio_repo_dir> <audiobooks_repo_dir> <out_dir>

라디오
- 모든 하위 폴더의 .m3u를 읽고 정규화한 URL로 중복 제거
  (http/https, 끝의 '/' 또는 '/;', 추적 파라미터, 프록시 래퍼를 같은 주소로 취급).
- 각 방송이 들어 있던 플레이리스트 파일명을 국가 / 언어 / 장르 태그로 분류하고,
  가장 많이 나온 값을 대표값으로 사용 (geo_lang.py, GENRE_RULES 참고).
- 국가 태그가 없으면 스트림 주소의 국가 도메인(.de, .br …)으로 추정  → "country_inferred": true
- 언어 태그가 없으면 같은 국가 방송들의 최다 언어로 추정         → "language_inferred": true
- 출력: out/radio/<country>.json  {country, count, languages: {lang: {count, genres: {genre: {count, stations}}}}}

오디오북 (archive.org 파일 링크, 실시간 방송 아님)
- 최상위 폴더(컬렉션)별 out/audiobooks/<collection>.json, 플레이리스트 단위, 오디오 파일만, URL 중복 제거.

out/index.json 에 전체 트리와 개수 요약.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_lang import COUNTRY_CODE, LANGUAGE_CODE, NOISE, classify_name, country_from_host  # noqa: E402

# (genre, regex) — 위에서부터 먼저 일치하는 규칙 적용. 정규화된 파일명(소문자, 구분자 '_')에 대해 검사.
GENRE_RULES = [
    ("decade_1920s_50s", r"^(19)?[2-5]0s$|^(19)?[2-5]0s_"),
    ("decade_60s", r"^(19)?60(s|er)"),
    ("decade_70s", r"^(19)?70(s|er)"),
    ("decade_80s", r"^(19)?80(s|er)"),
    ("decade_90s", r"^(19)?90(s|er)"),
    ("decade_2000s", r"^(00s|2000s|10s|2010s)"),
    ("smooth_jazz", r"smooth_?jazz"),
    ("acid_jazz", r"acid_?jazz|nu_?jazz"),
    ("jazz", r"jazz|bebop|dixieland"),
    ("big_band_swing", r"big_?band|swing"),
    ("blues", r"blues"),
    ("soul_rnb_funk", r"soul|r_?n_?b|r_and_b|^r_b$|^r&b$|^rb$|rhythm_and_blues|funk|motown|groove"),
    ("hip_hop_rap", r"hip_?hop|^rap|_rap$|trap$|grime|urban"),
    ("reggae_ska", r"reggae|ska$|^ska|dancehall|ragga|^dub$|roots_reggae"),
    ("metal", r"metal|grindcore|deathcore"),
    ("punk", r"punk|emo$|hardcore_punk"),
    ("gothic_industrial", r"goth|industrial|darkwave|ebm|dark_?wave"),
    ("alternative_indie", r"alternative|indie|grunge|britpop|shoegaze|post_?rock|^aaa$"),
    ("rock", r"rock"),
    ("country", r"country|americana|bluegrass|honky|western|tejano"),
    ("folk", r"folk|celtic|acoustic|singer|chanson|fado|volksmusik"),
    ("drum_and_bass", r"drum_?(and|n|&)_?bass|^dnb|jungle|breakbeat|breaks|dubstep|bass$"),
    ("trance_goa", r"trance|goa|psy"),
    ("techno", r"techno|minimal|hardstyle|hardcore|gabber|rave"),
    ("house", r"house|garage|club|^edm$"),
    ("disco_eurodance", r"disco|eurodance|euro_?pop|italo|hi_?nrg|freestyle"),
    ("electronic", r"electro|glitch|new_?wave|^wave$|synth|idm|experimental|^dj$|dance|remix"),
    ("chillout_lounge", r"chill|lounge|downtempo|trip_?hop"),
    ("ambient_relax", r"ambient|relax|meditation|new_?age|zen|spa$|nature|sleep|calm"),
    ("classical", r"classical|klassik|clasica|^early$|medieval|classic_?music|baroque|symphon|orchestra|chamber|piano|^classics?$"),
    ("opera", r"opera"),
    ("easy_listening", r"easy|adult_?contemporary|soft|^ac$|hot_?ac|instrumental|standards|romantic|love|ballad|slow|vocal"),
    ("soundtrack", r"soundtrack|film|movie|cinema|musical|anime|game|broadway"),
    ("oldies", r"oldies|old_school|classic_?hits|retro|nostalgia|golden"),
    ("jpop_kpop_asia", r"j_?pop|k_?pop|c_?pop|mandopop|cantopop|enka"),
    ("bollywood_indian", r"bollywood|bhangra|desi|filmi|bhakti|carnatic|hindustani"),
    ("latin", r"latin|salsa|reggaeton|merengue|bachata|cumbia|tango|samba|bossa|tropical|ranchera|banda|grupera|norte|mariachi|vallenato|bolero|sertanej|forro|kizomba|zouk|kompa|soca|calypso|balada|regional_mex"),
    ("schlager_polka", r"schlager|discofox|polka|manele|chalga|turbo_?folk|arabesk"),
    ("world", r"world|^african$|^asian$|^indian$|ethnic|afro|african_music|oriental|caribbean|hawaiian|tribal|traditional|international"),
    ("news_talk", r"news|noticias|nachrichten|reading_service|poetry|talk|politic|information|business|weather|traffic|public|government|podcast|spoken|scanner|police|emergency|fire|current_affairs|drama"),
    ("pop_hits", r"pop|top_?\d*|hits|charts|mainstream|cht$|current"),
    ("christian_gospel", r"christian|gospel|worship|praise|catholic|church|religio|spiritual"),
    ("islamic_quran", r"quran|islam|nasheed"),
    ("sports", r"sport|^spor$|football|soccer|baseball"),
    ("comedy", r"comedy|humor|funny"),
    ("kids", r"kids|children|family"),
    ("holiday", r"christmas|xmas|holiday|halloween"),
    ("college_community", r"college|university|campus|community|student"),
    ("various_eclectic", r"various|variety|eclectic|mixed|^mix$|^misc"),
]
COMPILED = [(g, re.compile(rx)) for g, rx in GENRE_RULES]
# 대표 장르 선정 시 가중치 (연대/잡다 목록은 실제 장르보다 우선순위 낮음)
WEIGHT = defaultdict(lambda: 1.0, {g: 0.5 for g, _ in GENRE_RULES
                                    if g.startswith("decade_") or g in ("various_eclectic", "college_community", "pop_hits")})
# 방송 이름으로 장르를 강제 지정: (국가, 이름 정규식, 장르). 플레이리스트 태그보다 우선.
# 위에서부터 먼저 일치하는 규칙 적용.
GENRE_OVERRIDES = [
    ("South Korea", re.compile(r"\bKBS\b.*(classic|클래식)", re.I), "classical"),   # KBS 클래식FM
    ("South Korea", re.compile(r"\bKBS\b", re.I), "news_talk"),                     # 그 밖의 한국 KBS 방송은 뉴스/토크
]


def override_genre(country, name, genre):
    for c, rx, g in GENRE_OVERRIDES:
        if country == c and rx.search(name):
            return g
    return genre


SKIP_FILES = re.compile(r"^---")  # 저장소 전체 합본 파일(everything/sorted/randomized)
AUDIO_EXT = {"mp3", "ogg", "m4a", "m4b", "flac", "opus", "aac", "wav", "wma"}

_cache = {}


def classify(fname):
    """playlist file name -> list of (kind, value), kind in {'country','language','genre'}"""
    if fname in _cache:
        return _cache[fname]
    n = re.sub(r"\.m3u$", "", fname, flags=re.I).lower().replace("%26", "&")
    n = re.sub(r"[^a-z0-9&]+", "_", n).strip("_")
    res = classify_name(n)
    if not res:
        g = re.sub(r"(?:_?\d+)$", "", n) if not re.search(r"\d0s$", n) else n
        if g and g not in NOISE:
            for genre, rx in COMPILED:
                if rx.search(g):
                    res = [("genre", genre)]
                    break
    _cache[fname] = res
    return res


TRACKING_KEYS = re.compile(r"^(n|ref|platform|source|src|from|dist|type|t|ts|_|cb|rnd|random|nocache|timestamp|"
                           r"uuid|sid|listenerid|lsid|token|us_privacy|gdpr.*|aw_.*|listening[-_]from.*|utm_.*|amsparams|"
                           r"siteid|site_id|plugin_id|player|ua|icy)$", re.I)
STREAM_EXT = re.compile(r"(?:_sc)?(?:\.(?:mp3|aac|aacp|flv|ogg|opus|m3u8?|pls))?$", re.I)


def norm_url(u, _depth=0):
    """dedup key: scheme-less host + path; tracking params, trailing '/;' and format suffixes removed."""
    u = u.strip()
    try:
        p = urlsplit(u)
    except ValueError:
        return None
    if p.scheme.lower() not in ("http", "https", "mms", "rtmp", "rtsp") or not p.netloc:
        return None
    params = [kv.split("=", 1) for kv in p.query.split("&") if kv]
    # 프록시 래퍼 (…/?q=http://real.stream/…) 는 실제 주소 기준
    for kv in params:
        if len(kv) == 2 and re.match(r"https?(:|%3a)", kv[1], re.I) and _depth < 2:
            from urllib.parse import unquote
            inner = norm_url(unquote(kv[1]), _depth + 1)
            if inner:
                return inner
    host = p.netloc.lower().split("@")[-1]
    host = re.sub(r":(80|443)$", "", host)
    path = re.sub(r"/;?$", "", p.path)
    path = STREAM_EXT.sub("", path) if host.endswith("streamtheworld.com") else re.sub(r"/;?$", "", path)
    keep = sorted("=".join(kv) for kv in params if not TRACKING_KEYS.match(kv[0]))
    return f"{host}{path}{'?' + '&'.join(keep) if keep else ''}"  # http/https 동일 취급


def better_url(old, new):
    """같은 방송의 여러 주소 중 https > 추적 파라미터 적은(짧은) 주소 선호"""
    ko = (old.startswith("https://"), -len(old))
    kn = (new.startswith("https://"), -len(new))
    return new if kn > ko else old


EXTINF = re.compile(r"#EXTINF:[^,]*?(?:\s+(?P<attrs>[a-z\-]+=\".*\"))?\s*,\s*(?P<name>.*)$", re.I)
ATTR = re.compile(r'([a-z\-]+)="([^"]*)"', re.I)
BITRATE = re.compile(r"\s*-\s*(\d{2,4})\s*kbit/s\s*$", re.I)


def parse_m3u(path):
    name = attrs = None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.upper().startswith("#EXTINF"):
                    m = EXTINF.match(line)
                    name = (m.group("name").strip() if m else None) or None
                    attrs = dict(ATTR.findall(line))
                elif line.startswith("#"):
                    continue
                else:
                    yield line, name, attrs or {}
                    name = attrs = None
    except OSError:
        return


def build_radio(root, out):
    stations = {}  # key -> dict
    files = 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for fn in fns:
            if not fn.lower().endswith(".m3u") or SKIP_FILES.match(fn):
                continue
            files += 1
            tags = classify(fn)
            for url, name, attrs in parse_m3u(os.path.join(dp, fn)):
                key = norm_url(url)
                if not key:
                    continue
                s = stations.get(key)
                if s is None:
                    s = stations[key] = {"url": url, "names": Counter(), "genre": Counter(),
                                         "country": Counter(), "language": Counter(),
                                         "logo": None, "bitrate": None}
                s["url"] = better_url(s["url"], url)
                if name:
                    bm = BITRATE.search(name)
                    if bm:
                        s["bitrate"] = s["bitrate"] or int(bm.group(1))
                        name = BITRATE.sub("", name)
                    if name.strip():
                        s["names"][name.strip()] += 1
                for kind, val in tags:
                    s[kind][val] += 1
                logo = attrs.get("tvg-logo")
                if logo and not s["logo"]:
                    s["logo"] = logo

    order = [g for g, _ in GENRE_RULES]

    def top(counter, weight=None):
        if not counter:
            return None
        return max(counter.items(), key=lambda kv: (kv[1] * (weight[kv[0]] if weight else 1),
                                                     -order.index(kv[0]) if weight else 0, kv[0]))[0]

    # 1차: 명시적 국가/언어/장르
    for s in stations.values():
        s["c"] = top(s["country"])
        s["c_inferred"] = False
        if not s["c"]:
            s["c"] = country_from_host(urlsplit(s["url"]).netloc.lower())
            s["c_inferred"] = bool(s["c"])
        s["c"] = s["c"] or "Unknown"
        s["l"] = top(s["language"])
        s["g"] = top(s["genre"], WEIGHT) or "unclassified"

    # 언어 추정 기준은 명시적 국가 태그가 있는 방송만 사용
    # 언어 정보가 없는 방송은 같은 국가 방송들의 최다 언어로 추정 (Multilingual 제외)
    lang_by_country = defaultdict(Counter)
    for s in stations.values():
        if s["l"] and s["l"] != "Multilingual" and not s["c_inferred"]:
            lang_by_country[s["c"]][s["l"]] += 1
    inferred = 0
    for s in stations.values():
        s["inferred"] = False
        if not s["l"]:
            guess = lang_by_country[s["c"]].most_common(1)
            if s["c"] != "Unknown" and guess:
                s["l"], s["inferred"] = guess[0][0], True
                inferred += 1
            else:
                s["l"] = "Unknown"

    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for s in stations.values():
        rec = {"name": s["names"].most_common(1)[0][0] if s["names"] else s["url"], "url": s["url"]}
        if s["bitrate"]:
            rec["bitrate"] = s["bitrate"]
        if s["logo"]:
            rec["logo"] = s["logo"]
        if len(s["genre"]) > 1:
            rec["tags"] = [g for g, _ in s["genre"].most_common()]
        if s["c_inferred"]:
            rec["country_inferred"] = True
        if s["inferred"]:
            rec["language_inferred"] = True
        tree[s["c"]][s["l"]][override_genre(s["c"], rec["name"], s["g"])].append(rec)

    rdir = os.path.join(out, "radio")
    os.makedirs(rdir, exist_ok=True)
    index = {}
    for country in sorted(tree):
        langs = tree[country]
        doc = {"country": country, "count": 0, "languages": {}}
        idx = {"file": None, "code": COUNTRY_CODE.get(country), "count": 0, "languages": {}}
        for lang in sorted(langs, key=lambda k: -sum(map(len, langs[k].values()))):
            genres = langs[lang]
            lcount = sum(map(len, genres.values()))
            gd = {}
            for g in sorted(genres, key=lambda k: (k == "unclassified", k)):
                recs = sorted(genres[g], key=lambda r: r["name"].lower())
                gd[g] = {"count": len(recs), "stations": recs}
            doc["languages"][lang] = {"count": lcount, "genres": gd}
            idx["languages"][lang] = {"count": lcount, "genres": {g: v["count"] for g, v in gd.items()}}
            doc["count"] += lcount
        idx["count"] = doc["count"]
        fname = re.sub(r"[^a-z0-9]+", "_", country.lower()).strip("_") + ".json"
        idx["file"] = "radio/" + fname
        with open(os.path.join(rdir, fname), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        index[country] = idx
    print(f"radio: language inferred from country for {inferred} stations")
    return files, len(stations), index


def build_audiobooks(root, out):
    os.makedirs(os.path.join(out, "audiobooks"), exist_ok=True)
    seen = set()
    index = {}
    total_urls = dup = 0
    for coll in sorted(os.listdir(root)):
        cdir = os.path.join(root, coll)
        if not os.path.isdir(cdir) or coll.startswith("."):
            continue
        playlists = []
        for dp, dns, fns in os.walk(cdir):
            dns.sort()
            for fn in sorted(fns):
                if not fn.lower().endswith(".m3u"):
                    continue
                tracks = []
                for url, _, _ in parse_m3u(os.path.join(dp, fn)):
                    ext = url.rsplit(".", 1)[-1].lower()
                    if ext not in AUDIO_EXT:
                        continue
                    if url in seen:
                        dup += 1
                        continue
                    seen.add(url)
                    tracks.append(url)
                if tracks:
                    total_urls += len(tracks)
                    sub = os.path.relpath(dp, cdir)
                    playlists.append({"title": fn[:-4].replace("_", " "),
                                      **({"folder": sub} if sub != "." else {}),
                                      "tracks": tracks})
        if playlists:
            slug = re.sub(r"[^a-z0-9]+", "_", coll.lower()).strip("_")
            with open(os.path.join(out, "audiobooks", f"{slug}.json"), "w", encoding="utf-8") as f:
                json.dump({"collection": coll, "playlists": len(playlists),
                           "tracks": sum(len(p["tracks"]) for p in playlists),
                           "items": playlists}, f, ensure_ascii=False, separators=(",", ":"))
            index[slug] = {"playlists": len(playlists), "tracks": sum(len(p["tracks"]) for p in playlists)}
    return total_urls, dup, index


def main():
    radio_root, ab_root, out = sys.argv[1:4]
    files, uniq, rindex = build_radio(radio_root, out)
    print(f"radio: {files} m3u files, {uniq} unique stations, {len(rindex)} countries")
    turls, dup, aindex = build_audiobooks(ab_root, out)
    print(f"audiobooks: {turls} unique audio urls ({dup} duplicates removed), {len(aindex)} collections")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"radio": {"total": uniq, "hierarchy": "country > language > genre", "countries": rindex,
                             "language_codes": {l: LANGUAGE_CODE[l] for l in sorted({l for c in rindex.values() for l in c["languages"]}) if l in LANGUAGE_CODE}},
                   "audiobooks": aindex}, f, ensure_ascii=False, indent=1)
    import featured  # noqa: E402  (imports this module, so not at the top)
    featured.apply(out)


if __name__ == "__main__":
    main()
