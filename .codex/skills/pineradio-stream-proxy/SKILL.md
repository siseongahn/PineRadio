---
name: pineradio-stream-proxy
description: Install, update, verify or troubleshoot how https://digipine.com/radio/ is served — the PineRadio stream relay (tools/stream_proxy.py behind nginx) that lets plain-http radio streams play on the https site, and the nginx rules for which repo files are public (index.html, data/, icons/, manifest.webmanifest) and which must stay hidden (tools/, deploy/, dotfiles). Use when http stations fail to play on the https site ("Mixed Content", "automatically upgraded to HTTPS", "재생할 수 없는 스트림", "http 방송 재생 안 됨"), when a site file returns 404 on the server (e.g. manifest.webmanifest, icons), when setting up the server, or after changing tools/stream_proxy.py, the station data or the set of top-level site files.
---

# PineRadio hosting and stream relay

## Why it exists
`https://digipine.com/radio/` is served over https. Browsers block plain-http audio on https pages:
they "upgrade" `http://` stream URLs to `https://`, and most radio servers don't speak https, so those
stations fail. About 42% of stations (≈313k) are http-only.

On https, `index.html` sends http streams to `stream?u=<url-encoded http url>`, which is relative to
the page, so the browser requests `/radio/stream?...`. nginx forwards that to
`tools/stream_proxy.py` on `127.0.0.1:8090`, which fetches the stream and relays it. On
http/localhost the page plays streams directly and the relay isn't used.

Files in this repo:
- `tools/stream_proxy.py`: the relay (Python 3.9+ standard library only, asyncio).
- `deploy/nginx-stream-proxy.conf`: the `location = /radio/stream` block.
- `deploy/pineradio-stream.service`: the systemd unit (runs unprivileged as a DynamicUser).
- `index.html`: `playableUrl()` sends http URLs through the relay when `location.protocol === "https:"`.

## Current status (last checked 2026-11-25)
Checked from outside with curl:

| Item | Status |
|---|---|
| Relay | Installed and working. `/radio/stream?u=<http station>` → `200 audio/mpeg`. |
| Site files | `index.html`, `data/…`, `icons/favicon.ico`, `icons/*.png` → 200. |
| `manifest.webmanifest` | **404**. nginx's public allowlist doesn't include it yet; fix it as described in "Public files" below. |
| Private paths | `tools/…` and `deploy/…` → 404, `.git/…` and `.codex/…` → 403. Correct, keep it that way. |

Re-run the checks in "Verify" before trusting this table.

## Public files (what nginx may serve)
The checkout contains more than the website, so nginx must serve only these:

| Path under `/radio/` | Content type | Notes |
|---|---|---|
| `index.html` (and `/radio/` itself) | `text/html` | the whole app |
| `data/**.json` | `application/json` | station and audiobook data; gzip helps a lot (16–50 MB files) |
| `icons/*.png`, `icons/favicon.ico` | `image/png`, `image/x-icon` | favicon, apple-touch-icon, manifest icons, header logo |
| `manifest.webmanifest` | `application/manifest+json` | home-screen install metadata |
| `stream` | proxied | the relay, see below |

Never serve `tools/`, `deploy/`, `.git/`, `.codex/`, `.forgejo/`, `README.md` or `*.py`.

The live config already allows everything except the manifest. How to add it depends on how the
`/radio/` location filters files, so look at the config first (`sudo nginx -T | grep -n -A15 'location.*radio'`):
- **Extension list** (e.g. `location ~ \.(html|json|png|ico)$`): add `webmanifest` to the list.
  Make sure `mime.types` maps it with `application/manifest+json webmanifest;` (nginx ≥ 1.21
  ships this; otherwise add a `types { application/manifest+json webmanifest; }` block).
- **Explicit locations**: add one for the file:
  ```nginx
  location = /radio/manifest.webmanifest {
      alias /srv/pineradio/manifest.webmanifest;
      default_type application/manifest+json;
  }
  ```

Then `sudo nginx -t && sudo systemctl reload nginx`.

Whenever a new top-level site file or folder is added to the repo, update this table and the nginx
allowlist in the same change.

## Server layout assumptions
- The live checkout is `/srv/pineradio` (the Forgejo workflow `.forgejo/workflows/deploy.yml`
  fast-forwards it on every push to `main`).
- nginx serves `https://digipine.com/radio/` from that checkout.
- Confirm both before changing anything. If paths differ, adjust `ExecStart` in the unit file and the
  location path in the nginx snippet.

## Install (one time, needs sudo on the server)
1. Check Python: `python3 --version` (3.9+).
2. Try the relay by hand:
   ```sh
   python3 -I /srv/pineradio/tools/stream_proxy.py --data /srv/pineradio/data --port 8090
   ```
   Expect `allowlist: ~172000 http stream hosts` and then `listening on 127.0.0.1:8090` within a few
   seconds. Stop it with Ctrl-C.
3. Install the service:
   ```sh
   sudo cp /srv/pineradio/deploy/pineradio-stream.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now pineradio-stream
   systemctl status pineradio-stream --no-pager
   ```
   - Optional: set `Environment=PINERADIO_PROXY_SECRET=<random hex>` in the unit (see the comment there).
     A fixed key keeps signed HLS segment URLs valid across restarts. Without it, a random key is
     used per start.
4. Add the nginx location:
   - Paste the contents of `deploy/nginx-stream-proxy.conf` into the `server { }` block for
     `digipine.com` (the one that serves `/radio/`). Or `include` the file from there.
   - It must be inside the TLS server block, not a separate server.
   - Then test and reload:
     ```sh
     sudo nginx -t && sudo systemctl reload nginx
     ```

## Verify
Run these from any machine:
```sh
# 1. relays a known http station → 200/206 with an audio content-type and bytes flowing
curl -s -o /dev/null -m 6 -w '%{http_code} %{content_type} %{size_download}\n' \
  'https://digipine.com/radio/stream?u=http%3A%2F%2Fsc2.radiocaroline.net%3A8040%2Fstream%2F1%2F'

# 2. refuses hosts that are not in the station data → 403
curl -s -m 6 -w ' %{http_code}\n' 'https://digipine.com/radio/stream?u=http%3A%2F%2Fexample.com%2F'

# 3. refuses internal addresses → 403
curl -s -m 6 -w ' %{http_code}\n' 'https://digipine.com/radio/stream?u=http%3A%2F%2F127.0.0.1%2F'
```

Static files and privacy, also from any machine:
```sh
B=https://digipine.com/radio
# must be 200 with the right type
for p in / icons/favicon.ico icons/favicon-32.png icons/apple-touch-icon.png manifest.webmanifest data/index.json; do
  curl -s -o /dev/null -m 10 -w "%{http_code} %{content_type} /$p\n" "$B/$p"; done
# must NOT be 200
for p in tools/stream_proxy.py deploy/pineradio-stream.service .git/HEAD .codex/skills/pineradio-stream-proxy/SKILL.md README.md; do
  curl -s -o /dev/null -m 10 -w "%{http_code} /$p\n" "$B/$p"; done
```

Then open https://digipine.com/radio/ and play an http station (hover a row to see its URL). In
DevTools → Network, the request should go to `stream?u=…` with status 200. The console should show
no "Mixed Content" warning for audio.

The first test station may be offline someday. If it fails, pick another `http://` URL from
`data/radio/*.json` before concluding the relay is broken.

## Updating
- **New public site file** (like `manifest.webmanifest` or `icons/`): allow it in nginx (see "Public files"). The deploy workflow copies the file to the server, but nginx won't serve a path it doesn't allow.
- **Station data changes** (`data/` rebuilt and pushed): no action needed. The relay reloads its
  allowlist within 60 s of `data/index.json` changing.
- **`tools/stream_proxy.py` changes**: the deploy workflow only fast-forwards the checkout, so restart
  the service after the push is deployed: `sudo systemctl restart pineradio-stream`.
- **Unit file changes**: copy it again, then `sudo systemctl daemon-reload && sudo systemctl restart pineradio-stream`.

## Troubleshooting
| Symptom | Likely cause / fix |
|---|---|
| `manifest.webmanifest` (or another new site file) returns 404 | nginx allowlist doesn't include it. See "Public files". Check that the file exists in `/srv/pineradio` first. |
| Private path (`tools/`, `deploy/`, `.git/`) returns 200 | nginx is serving the whole checkout. Restrict the `/radio/` location to the files in "Public files" right away. |
| `/radio/stream` returns 404 (nginx HTML page) | nginx location missing or in the wrong `server` block. Add it inside the https block for digipine.com and reload. |
| 502 Bad Gateway from nginx | Relay not running. Check `systemctl status pineradio-stream` and `journalctl -u pineradio-stream -n 50`. |
| 403 `host is not a known radio station` | The URL's host:port isn't in `data/radio/*.json` (by design), or the allowlist hasn't reloaded yet (wait 60 s or restart). |
| 403 `destination is not a public address` | The host resolves to a private/loopback address. This is refused on purpose (SSRF guard). |
| 403/404 with an HTML body from the station | The radio server itself refused or is gone (geo-blocking is common for US streams, e.g. streamtheworld). Not a relay bug. |
| 429 `too many streams` | Limits hit: 300 total or 6 per client IP (`MAX_TOTAL`, `MAX_PER_CLIENT` in the script). nginx must pass `X-Real-IP`, otherwise every listener looks like 127.0.0.1. |
| Audio stops after ~60 s | nginx is buffering or timing out. Make sure `proxy_buffering off` and `proxy_read_timeout 1h` are in the location. |
| Startup crash while loading the allowlist | A malformed URL in the data. `host_key()` must return `None` for it; check the traceback in journalctl. |

## Safety rules (keep these if you modify the relay)
- **Allowlist:** relay only `http://` URLs whose `host:port` appears in the station data. URLs the relay
  itself emits (HLS sub-playlists and segments, playlist hops) are allowed through an HMAC signature
  (`s=` parameter) instead.
- **Public addresses only:** resolve every hop and refuse it unless all addresses are public
  (`ip.is_global`). Connect to the checked IP, not the hostname, to avoid DNS rebinding.
- **Redirects and playlists:** follow redirects and `.pls`/`.m3u`/`.asx` playlists for at most 5 hops.
  If a hop lands on an `https://` URL, return it to the browser as a 302 instead of relaying.
- **Limits:** keep the connection limits. Never relay methods other than GET.
- **Local test:**
  ```sh
  python3 -I tools/stream_proxy.py --data data --port 8090
  ```
  Then request `http://127.0.0.1:8090/radio/stream?u=<encoded url>`.
