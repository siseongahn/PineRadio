# PineRadio

PineRadio is a browser player for about 746,000 internet radio stations and about 1.27 million audiobook tracks.

- **Radio:** stations are deduplicated and grouped by **country › language › genre** (239 countries, 50 genres).
- **Audiobooks:** the tracks are archive.org files, grouped into 44 collections of playlists.
- **Player:** search, favorites, HLS playback and 9 interface languages, all in a single `index.html` with no build step.
- **Data tools:** Python scripts convert m3u playlists into the JSON the player reads.

## Quick start

Browsers block `fetch()` on pages opened as `file://`, so serve the folder over HTTP:

```sh
git clone https://git.digipine.com/simon/PineRadio.git
cd PineRadio
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Features

- **Browse radio:** pick a country in the sidebar, then narrow down with language and genre filters.
- **Browse audiobooks:** pick a collection, then expand a playlist to see its tracks. Tracks play one after another.
- **Search:** matches station names and URLs. A search can cover the current selection or every country and collection; the "everywhere" search loads files in the background and shows results as they arrive.
- **Favorites:** saved in the browser's `localStorage`.
- **Playback:** plain audio streams and HLS (`.m3u8`, via [hls.js](https://github.com/video-dev/hls.js)). Previous/next follows the current result list.
- **Keyboard and media keys:** <kbd>Space</kbd> plays or pauses, <kbd>/</kbd> jumps to the search box, and the OS media keys work through the Media Session API.
- **Interface languages:** English (default), Simplified Chinese, Traditional Chinese, French, German, Japanese, Korean, Russian and Spanish.
  - UI text and genre names are translated in the page itself.
  - Country and language names come from the browser's `Intl.DisplayNames`.
- **Themes:** light and dark mode follow the system setting.

## Repository layout

```
index.html              web player (HTML, CSS and JS in one file)
data/
  index.json            summary: counts per country / language / genre, ISO codes, file paths
  radio/<country>.json  one file per country
  audiobooks/<name>.json one file per collection
tools/
  build_stations.py     m3u → JSON converter
  geo_lang.py           country, language and ISO code tables used for classification
```

### Radio file format

```json
{
  "country": "South Korea",
  "count": 490,
  "languages": {
    "Korean": {
      "count": 464,
      "genres": {
        "jazz": {
          "count": 9,
          "stations": [
            {
              "name": "Example FM",
              "url": "https://example.com/stream",
              "bitrate": 128,
              "logo": "https://example.com/logo.png",
              "tags": ["jazz", "blues"],
              "language_inferred": true
            }
          ]
        }
      }
    }
  }
}
```

The `bitrate`, `logo`, `tags`, `country_inferred` and `language_inferred` fields are optional.

### Audiobook file format

```json
{
  "collection": "old_time_radio",
  "playlists": 8048,
  "tracks": 156709,
  "items": [
    { "title": "…", "folder": "01", "tracks": ["https://archive.org/download/…/….mp3"] }
  ]
}
```

## Rebuilding the data

The JSON in `data/` is generated from two m3u playlist collections:

- [junguler/m3u-radio-music-playlists](https://github.com/junguler/m3u-radio-music-playlists)
- [junguler/m3u-audiobooks](https://github.com/junguler/m3u-audiobooks)

Download both, then run:

```sh
python3 -I tools/build_stations.py <m3u-radio-music-playlists dir> <m3u-audiobooks dir> data
```

A full rebuild takes about 1–2 minutes and needs only the Python 3 standard library.

### How stations are classified

- **Deduplication:** every URL is normalized before comparison. http and https count as the same address, and the following are ignored:
  - trailing `/` or `/;`
  - tracking parameters such as `?n=` and `?ref=`
  - proxy wrappers (`?q=<real url>`)
  - Streamtheworld format suffixes

  When a station has several addresses, the https one with the fewest extra parameters is kept.
- **Tags:** the name of each playlist a station appears in is read as a country, a language or a genre. For example:
  - `rock.m3u` → genre
  - `lang-spa.m3u` → language
  - `loca_br.m3u` → country
  - `Portuguese_(Brazil).m3u` → language and country

  The most frequent value of each kind becomes the station's country, language and genre.
- **Inference:**
  - If a station has no country tag, the country is taken from the stream's country-code domain (`.de`, `.br`, …) and marked with `country_inferred`.
  - If a station has no language tag, it gets the most common language among stations from the same country and is marked with `language_inferred`.
- **Unclassified stations:** stations with no usable country end up in `radio/unknown.json`. Stations with no genre are filed under `unclassified`.

To adjust the rules, edit `GENRE_RULES` in `tools/build_stations.py` or the tables in `tools/geo_lang.py`, then rebuild.

## Stream relay for https hosting

Browsers block plain-http audio on https pages, and about 42% of the stations are http-only. When the
page is served over https, it sends `http://` streams through a small relay at `./stream?u=<url>`:

- `tools/stream_proxy.py`: the relay. It uses only the Python standard library and follows redirects, `.pls`/`.m3u` playlists and HLS.
- `deploy/nginx-stream-proxy.conf`: the nginx `location` that forwards to the relay.
- `deploy/pineradio-stream.service`: the systemd unit.

The relay only accepts hosts that appear in the station data and refuses private or loopback
addresses, so it is not an open proxy. Install and troubleshooting steps are in
`.codex/skills/pineradio-stream-proxy/SKILL.md`. On `http://localhost` the relay is not needed.

## Known limitations

- **Dead stations:** the source lists are crowdsourced and change constantly, so many stations will be offline. The player reports these as playback errors.
- **Playlist URLs:** some URLs point to playlist files (`.pls`, `.m3u`) rather than streams, and browsers cannot play those directly.
- **Large files:** the biggest files take a moment to load the first time, then stay cached in memory:
  - `unknown.json` 22 MB
  - `united_states.json` 16 MB
  - `librivox.json` 48 MB
- **Audiobook search:** searching all audiobooks downloads about 140 MB on first use.

## Credits

- Station and audiobook lists: [junguler](https://github.com/junguler)'s m3u playlist repositories.
- Audiobook and recording files: hosted by the [Internet Archive](https://archive.org).
- HLS playback: [hls.js](https://github.com/video-dev/hls.js).
