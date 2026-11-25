# PineRadio

PineRadio is a browser player for about 746,000 internet radio stations and about 106,000 audiobooks (1.27 million tracks).

**Live site:** <https://digipine.com/radio/>

- **Radio:** stations are deduplicated and grouped by **country › language › genre** (239 countries, 50 genres).
- **Audiobooks:** the tracks are archive.org files, grouped into 44 collections of playlists.
- **Player:** search, favorites, HLS playback and 9 interface languages, all in a single `index.html` with no build step.
- **Data tools:** Python scripts convert m3u playlists into the JSON the player reads.
- **Stream relay:** a small server-side relay lets http-only stations play on the https site.

## Quick start

Browsers block `fetch()` on pages opened as `file://`, so serve the folder over HTTP:

```sh
git clone https://git.digipine.com/simon/PineRadio.git
cd PineRadio
python3 -m http.server 8000
```

Then open <http://localhost:8000>. Locally the page plays every stream directly, so the relay isn't needed.

## Features

### Browsing and search
- **Header totals:** the header shows the total number of stations and audiobooks, read from `data/index.json`. Hover it to see the track and collection counts.
- **Radio:** pick a country in the sidebar, then narrow down with language and genre filters.
- **All countries:** the first sidebar entry lists every station.
  - The filter counts show at once, read from `data/index.json`.
  - Stations load country by country, largest first, and show up as they arrive.
  - Long filter rows (116 languages) collapse to the top 20 with a "+N more" toggle.
- **Audiobooks:** pick a collection, then expand a playlist to see its tracks. Tracks play one after another.
- **Search:** matches station names and URLs.
  - It can cover the current selection or everything.
  - The "everywhere" search loads files in the background and shows results as they arrive.
- **Favorites:** stations and playlists, saved in the browser.

### Playback
- **Formats:** plain audio streams and HLS (`.m3u8`, via [hls.js](https://github.com/video-dev/hls.js)).
- **Previous/next:** follows the current result list, or the playlist for audiobooks.
- **Keyboard and media keys:** <kbd>Space</kbd> plays or pauses and <kbd>/</kbd> jumps to the search box. The OS media keys work through the Media Session API.
- **http stations on https:** on the https site, `http://` streams go through the stream relay (see below). `http://` logos are skipped there, because browsers would block them.

### Languages
- **Interface languages:** English, Simplified Chinese, Traditional Chinese, French, German, Japanese, Korean, Russian and Spanish.
  - UI text and genre names are translated in the page.
  - Country and language names come from the browser's `Intl.DisplayNames`.
- **First visit:** the language is picked from the browser's language list (`navigator.languages`) and saved. If none of the 9 matches, English is used. Chinese tags `zh-TW`, `zh-HK` and `zh-Hant` map to Traditional, other `zh` tags to Simplified.
- **Later visits:** the saved choice is used until it is changed in the 🌐 menu.
- **Country order:** the sidebar lists the countries that speak the selected language first, then all others.
  - The country lists are in `LOCALE_COUNTRIES` in `index.html`.
  - Until a country is picked by hand, the first of those countries is selected.

### Look
- **App icon:** the PinePlayerPro app icon is used for the favicon, apple-touch-icon, web manifest and header logo.
- **Header name:** "PineRadio" is set in [Fugaz One](https://fonts.google.com/specimen/Fugaz+One).
  - It comes from Google Fonts, and only the glyphs of the name are downloaded.
  - If the font can't be loaded, the system font is used.
- **Themes:** light and dark mode follow the system setting.
- **Phone layout:** works at phone width.

## Repository layout

```
index.html                  web player (HTML, CSS and JS in one file)
manifest.webmanifest        home-screen install metadata
icons/                      favicon, apple-touch-icon, manifest icons, header logo
data/
  index.json                totals per country / language / genre, ISO codes, file paths
  radio/<country>.json      one file per country
  audiobooks/<name>.json    one file per collection
tools/
  build_stations.py         m3u → JSON converter
  geo_lang.py               country, language and ISO code tables used for classification
  stream_proxy.py           stream relay for the https site
deploy/
  nginx-stream-proxy.conf   nginx location for the relay
  pineradio-stream.service  systemd unit for the relay
.forgejo/workflows/deploy.yml   updates the live checkout on every push to main
.codex/skills/pineradio-stream-proxy/SKILL.md   Codex skill: hosting, relay setup, checks
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

> **Manual fixes are overwritten.** Edits made directly in `data/` are replaced by a rebuild. For
> example, commit `67a99b6` fixed the Mokpo FEBC stream URL in `data/radio/south_korea.json`. Re-apply
> such fixes after rebuilding, or move them into the build rules.

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

## Hosting

### Deployment
- **Automatic updates:** every push to `main` runs `.forgejo/workflows/deploy.yml`, which fast-forwards the live checkout (`/srv/pineradio`) on the server.
- **Public files:** nginx serves only the site files: `index.html`, `data/`, `icons/` and `manifest.webmanifest`. `tools/`, `deploy/` and dotfiles stay private.
- **New top-level site files:** must also be allowed in the nginx config.

### Stream relay for https
Browsers block plain-http audio on https pages, and about 42% of the stations are http-only. When the
page is served over https, it sends `http://` streams to `./stream?u=<url>`. nginx forwards that to
`tools/stream_proxy.py`, which fetches the stream and relays it.

What the relay handles:
- redirects, `.pls`/`.m3u`/`.asx` playlist URLs, HLS playlists, and old SHOUTcast `ICY` responses
- only the Python standard library is needed

How it stays safe:
- **Allowlist:** only hosts that appear in the station data are relayed. URLs the relay itself creates carry an HMAC signature instead.
- **Public addresses only:** each hop is resolved first and refused unless the address is public, which blocks requests into private networks.
- **Limits:** at most 300 concurrent streams in total and 6 per client.

Install, verification and troubleshooting steps are in the Codex skill
`.codex/skills/pineradio-stream-proxy/SKILL.md`. Two things to remember:
- After changing `tools/stream_proxy.py`, restart the service on the server (`sudo systemctl restart pineradio-stream`).
- After a data rebuild, nothing is needed: the relay reloads its allowlist within 60 seconds of `data/index.json` changing.

## Known limitations

- **Dead stations:** the source lists are crowdsourced and change constantly, so many stations will be offline. The player reports these as playback errors.
- **Region locks:** some stations refuse listeners from other regions (often US streams). The relay can't get around that.
- **Playlist URLs when testing locally:** URLs that point to playlist files (`.pls`, `.m3u`) can't be played directly by browsers. On the https site the relay resolves them.
- **Large files:** the biggest files take a moment to load the first time, then stay cached in memory:
  - `unknown.json` 22 MB
  - `united_states.json` 16 MB
  - `librivox.json` 48 MB
- **Audiobook search:** searching all audiobooks downloads about 140 MB on first use.

## Change history

| Commit | Change |
|---|---|
| `edd4e54` | Station data (country › language › genre), build tools and the web player with search, favorites, HLS and 9 UI languages |
| `dca7bf1` | README |
| `b0e5c01` | Forgejo workflow that deploys every push to `main` |
| `7d7d705` | Countries of the UI language listed first; UI language auto-detected on first visit and saved |
| `9e22478` | Codex skill for the stream relay setup |
| `9210863` | Stream relay so http-only stations play on the https site (`tools/stream_proxy.py`, `deploy/`) |
| `8242357` | PinePlayerPro app icon for favicon, header and web manifest |
| `67a99b6` | Fixed the Mokpo FEBC stream URL in the data |
| `873e194` | Codex skill extended to hosting: public files, status and checks |
| `2ef33f3` | Total station and audiobook counts in the header |
| `0e1c689` | README brought up to date with the work so far |
| `0708882` | "All countries" sidebar entry with progressive loading and collapsible filter chips |
| `4ade5a3` | README: "All countries" and change history |
| `7b49925` | Fugaz One font for the PineRadio name in the header |

## Credits

- Station and audiobook lists: [junguler](https://github.com/junguler)'s m3u playlist repositories.
- Audiobook and recording files: hosted by the [Internet Archive](https://archive.org).
- HLS playback: [hls.js](https://github.com/video-dev/hls.js).
- Icon: from the PinePlayerPro app.
