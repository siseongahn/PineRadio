#!/usr/bin/env python3
"""PineRadio stream proxy — relays http:// radio streams so they can play on the https site.

Browsers upgrade (and then fail) plain-http audio on https pages ("mixed content"). nginx forwards
/radio/stream?u=<http url> here, and this process fetches the stream and relays it.

Safety rules, so this is not an open proxy:
- Only http:// URLs whose host:port appears in the station data (data/radio/*.json) are accepted.
  URLs this proxy itself emits (HLS segments, redirect hops) carry an HMAC signature instead.
- Every hop is resolved first and refused unless all addresses are public (no loopback, LAN,
  link-local, …), and the connection goes to the checked address (no DNS-rebinding window).
- Limits on total and per-client connections.

Also handled: redirects (followed here; https targets are handed back to the browser), .pls/.m3u
playlist URLs (resolved to the first stream), HLS playlists (segment URLs rewritten through the
proxy), and old SHOUTcast "ICY 200 OK" responses.

usage: python3 -I stream_proxy.py [--data DIR] [--host 127.0.0.1] [--port 8090]
env:   PINERADIO_PROXY_SECRET  HMAC key for signed URLs (random per start if unset)
"""
import argparse
import asyncio
import glob
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
from urllib.parse import parse_qs, quote, urljoin, urlsplit

MAX_TOTAL = 300           # concurrent relayed streams
MAX_PER_CLIENT = 6        # per client IP (X-Real-IP from nginx)
CONNECT_TIMEOUT = 10
IDLE_TIMEOUT = 45         # no upstream bytes for this long → give up
MAX_HOPS = 5              # redirects + playlist indirections
PLAYLIST_LIMIT = 512 * 1024
UA = "PineRadio/1.0 (+stream relay)"
RELAY_HEADERS = {"content-type", "content-length", "transfer-encoding", "content-range", "accept-ranges"}
PLAYLIST_TYPES = ("audio/x-scpls", "audio/scpls", "audio/x-mpegurl", "audio/mpegurl", "application/x-mpegurl",
                  "application/vnd.apple.mpegurl", "video/x-ms-asf", "video/x-ms-asx", "audio/x-ms-wax")
PLAYLIST_EXT = re.compile(r"\.(pls|m3u|m3u8|asx|wax)$", re.I)

log = logging.getLogger("stream_proxy")
SECRET = (os.environ.get("PINERADIO_PROXY_SECRET") or secrets.token_hex(32)).encode()


class Refused(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


def sign(url):
    return hmac.new(SECRET, url.encode(), hashlib.sha256).hexdigest()[:32]


def host_key(url):
    """'host:port' of a URL, or None when the URL is malformed (e.g. a non-numeric port)."""
    try:
        p = urlsplit(url)
        return f"{(p.hostname or '').lower()}:{p.port or 80}" if p.hostname else None
    except ValueError:
        return None


def proxify(url):
    """URL to hand to the browser: https as-is, http through this proxy (signed)."""
    if url.lower().startswith("https://"):
        return url
    return f"stream?u={quote(url, safe='')}&s={sign(url)}"


# ---------- allowlist ----------
class Allowlist:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.hosts = frozenset()
        self.stamp = None

    def _stamp(self):
        try:
            return os.stat(os.path.join(self.data_dir, "index.json")).st_mtime
        except OSError:
            return None

    def _load(self):
        hosts = set()
        for path in glob.glob(os.path.join(self.data_dir, "radio", "*.json")):
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            for lang in doc.get("languages", {}).values():
                for genre in lang.get("genres", {}).values():
                    for st in genre.get("stations", []):
                        url = st.get("url", "")
                        key = host_key(url) if url[:7].lower() == "http://" else None
                        if key:
                            hosts.add(key)
        return frozenset(hosts)

    async def refresh(self):
        stamp = self._stamp()
        if stamp == self.stamp and self.hosts:
            return
        hosts = await asyncio.to_thread(self._load)
        self.hosts, self.stamp = hosts, stamp
        log.info("allowlist: %d http stream hosts", len(hosts))

    async def watch(self):
        while True:
            await asyncio.sleep(60)
            try:
                await self.refresh()
            except Exception:
                log.exception("allowlist refresh failed")


# ---------- upstream ----------
async def resolve_public(host, port):
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), CONNECT_TIMEOUT)
    except (OSError, asyncio.TimeoutError):
        raise Refused(502, "cannot resolve host")
    addrs = []
    for family, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise Refused(403, "destination is not a public address")
        addrs.append(sockaddr[0])
    if not addrs:
        raise Refused(502, "cannot resolve host")
    return addrs[0]


async def open_upstream(url, range_header=None):
    try:
        p = urlsplit(url)
        port = p.port or 80
    except ValueError:
        raise Refused(400, "malformed URL")
    if p.scheme.lower() != "http" or not p.hostname:
        raise Refused(400, "only http:// URLs are relayed")
    ip = await resolve_public(p.hostname, port)
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), CONNECT_TIMEOUT)
    except (OSError, asyncio.TimeoutError):
        raise Refused(502, "upstream connection failed")
    host = p.hostname if ":" not in p.hostname else f"[{p.hostname}]"
    if port != 80:
        host += f":{port}"
    target = (p.path or "/") + (f"?{p.query}" if p.query else "")
    lines = [f"GET {target} HTTP/1.1", f"Host: {host}", f"User-Agent: {UA}", "Accept: */*", "Connection: close"]
    if range_header:
        lines.append(f"Range: {range_header}")
    writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1", "replace"))
    try:
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), IDLE_TIMEOUT)
        m = re.match(rb"^(?:HTTP/\d(?:\.\d)?|ICY)\s+(\d{3})\s*(.*?)\r?\n$", status_line)
        if not m:
            raise Refused(502, "upstream sent an invalid response")
        headers = []
        for _ in range(200):
            line = await asyncio.wait_for(reader.readline(), IDLE_TIMEOUT)
            if line in (b"\r\n", b"\n", b""):
                break
            k, _, v = line.decode("latin-1").partition(":")
            headers.append((k.strip(), v.strip()))
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError):
        writer.close()
        raise Refused(502, "upstream did not answer")
    except Refused:
        writer.close()
        raise
    return int(m.group(1)), m.group(2).decode("latin-1"), headers, status_line.startswith(b"ICY"), reader, writer


def hget(headers, name):
    name = name.lower()
    for k, v in headers:
        if k.lower() == name:
            return v
    return None


async def read_body(reader, headers, limit):
    """Read a small, complete body (playlists only); supports chunked encoding."""
    data = b""
    if (hget(headers, "transfer-encoding") or "").lower() == "chunked":
        while len(data) <= limit:
            size_line = await asyncio.wait_for(reader.readline(), IDLE_TIMEOUT)
            size = int(size_line.split(b";")[0].strip() or b"0", 16)
            if size == 0:
                break
            data += await asyncio.wait_for(reader.readexactly(size), IDLE_TIMEOUT)
            await reader.readline()
    else:
        length = hget(headers, "content-length")
        want = min(int(length), limit + 1) if length and length.isdigit() else limit + 1
        while len(data) < want:
            chunk = await asyncio.wait_for(reader.read(want - len(data)), IDLE_TIMEOUT)
            if not chunk:
                break
            data += chunk
    if len(data) > limit:
        raise Refused(502, "playlist too large")
    return data


def is_playlist(url, headers):
    """Whether an upstream reply is a playlist (pls/m3u/HLS/asx) rather than audio."""
    ctype = (hget(headers, "content-type") or "").split(";")[0].strip().lower()
    return ctype in PLAYLIST_TYPES or bool(PLAYLIST_EXT.search(urlsplit(url).path)
                                           and not ctype.startswith(("audio/mpeg", "audio/aac")))


def playlist_target(text, base):
    """First stream URL inside a .pls / .m3u / .asx playlist."""
    m = re.search(r"^\s*File\d+\s*=\s*(\S+)", text, re.I | re.M)                       # pls
    if not m:
        m = re.search(r"""<ref\s+href\s*=\s*["']([^"']+)""", text, re.I)               # asx
    if m:
        return urljoin(base, m.group(1).strip())
    for line in text.splitlines():                                                     # m3u
        line = line.strip()
        if line and not line.startswith("#"):
            return urljoin(base, line)
    return None


def rewrite_hls(text, base):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            line = proxify(urljoin(base, s))
        elif s.startswith("#") and 'URI="' in s:
            line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{proxify(urljoin(base, m.group(1)))}"', line)
        out.append(line)
    return "\n".join(out) + "\n"


# ---------- server ----------
class Proxy:
    def __init__(self, allow):
        self.allow = allow
        self.total = 0
        self.per_client = {}

    async def handle(self, reader, writer):
        client = None
        counted = False
        upstream_writer = None
        try:
            try:
                request_line = await asyncio.wait_for(reader.readline(), 15)
                headers = []
                for _ in range(100):
                    line = await asyncio.wait_for(reader.readline(), 15)
                    if line in (b"\r\n", b"\n", b""):
                        break
                    k, _, v = line.decode("latin-1").partition(":")
                    headers.append((k.strip(), v.strip()))
            except (asyncio.TimeoutError, OSError):
                return
            parts = request_line.decode("latin-1").split()
            if len(parts) != 3 or parts[0] != "GET":
                return await self.reply(writer, 405, "only GET is supported")
            target = urlsplit(parts[1])
            if not target.path.endswith("/stream"):
                return await self.reply(writer, 404, "not found")
            qs = parse_qs(target.query)
            url = (qs.get("u") or [""])[0]
            sig = (qs.get("s") or [""])[0]
            client = hget(headers, "x-real-ip") or (writer.get_extra_info("peername") or ("?",))[0]

            if not url.lower().startswith("http://"):
                return await self.reply(writer, 400, "only http:// URLs are relayed")
            key = host_key(url)
            if not ((key and key in self.allow.hosts) or (sig and hmac.compare_digest(sig, sign(url)))):
                return await self.reply(writer, 403, "host is not a known radio station")
            if self.total >= MAX_TOTAL or self.per_client.get(client, 0) >= MAX_PER_CLIENT:
                return await self.reply(writer, 429, "too many streams")
            self.total += 1
            self.per_client[client] = self.per_client.get(client, 0) + 1
            counted = True

            range_header = hget(headers, "range")
            for _ in range(MAX_HOPS + 1):
                # Safari always probes with "Range: bytes=0-1" before playing. A playlist must be read
                # whole, so never ask for a range of one: by URL, or (below) once its reply shows it is one.
                if PLAYLIST_EXT.search(urlsplit(url).path):
                    range_header = None
                status, reason, up_headers, icy, up_reader, upstream_writer = await open_upstream(url, range_header)
                if range_header and (400 <= status < 500 or (status == 206 and is_playlist(url, up_headers))):
                    # some servers fail any Range request (4xx); others answer a playlist with only the
                    # asked-for bytes (206 "[p") — retry the same URL without Range
                    upstream_writer.close()
                    upstream_writer = None
                    range_header = None
                    status, reason, up_headers, icy, up_reader, upstream_writer = await open_upstream(url)
                location = hget(up_headers, "location")
                if status in (301, 302, 303, 307, 308) and location:
                    upstream_writer.close()
                    upstream_writer = None
                    url = urljoin(url, location)
                    if url.lower().startswith("https://"):
                        return await self.reply(writer, 302, "", [("Location", url)])
                    continue
                if status in (200, 206) and is_playlist(url, up_headers):
                    body = await read_body(up_reader, up_headers, PLAYLIST_LIMIT)
                    upstream_writer.close()
                    upstream_writer = None
                    text = body.decode("utf-8", "replace")
                    if "#EXT-X-" in text:                      # HLS: relay playlist with rewritten URLs
                        return await self.reply(writer, 200, rewrite_hls(text, url),
                                                [("Content-Type", "application/vnd.apple.mpegurl")])
                    nxt = playlist_target(text, url)
                    if not nxt:
                        return await self.reply(writer, 502, "empty playlist")
                    url = nxt
                    if url.lower().startswith("https://"):
                        return await self.reply(writer, 302, "", [("Location", url)])
                    range_header = None
                    continue
                return await self.relay(writer, status, reason, up_headers, icy, up_reader)
            return await self.reply(writer, 508, "too many redirects")
        except Refused as e:
            await self.reply(writer, e.status, str(e))
        except (ConnectionError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            pass
        except Exception:
            log.exception("unexpected error")
            await self.reply(writer, 500, "internal error")
        finally:
            if upstream_writer:
                upstream_writer.close()
            if counted:
                self.total -= 1
                left = self.per_client.get(client, 1) - 1
                if left > 0:
                    self.per_client[client] = left
                else:
                    self.per_client.pop(client, None)
            try:
                writer.close()
            except Exception:
                pass

    async def relay(self, writer, status, reason, up_headers, icy, up_reader):
        out = [(k, v) for k, v in up_headers if k.lower() in RELAY_HEADERS]
        if icy and not hget(out, "content-type"):
            out.append(("Content-Type", "audio/mpeg"))
        head = f"HTTP/1.1 {status} {reason or 'OK'}\r\n"
        head += "".join(f"{k}: {v}\r\n" for k, v in out)
        head += "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n"
        writer.write(head.encode("latin-1", "replace"))
        await writer.drain()
        while True:
            chunk = await asyncio.wait_for(up_reader.read(64 * 1024), IDLE_TIMEOUT)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()

    async def reply(self, writer, status, body, extra=()):
        reasons = {200: "OK", 302: "Found", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
                   405: "Method Not Allowed", 429: "Too Many Requests", 500: "Internal Server Error",
                   502: "Bad Gateway", 508: "Loop Detected"}
        data = body.encode("utf-8")
        head = f"HTTP/1.1 {status} {reasons.get(status, 'Error')}\r\n"
        if not any(k.lower() == "content-type" for k, _ in extra):
            head += "Content-Type: text/plain; charset=utf-8\r\n"
        head += "".join(f"{k}: {v}\r\n" for k, v in extra)
        head += f"Content-Length: {len(data)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
        try:
            writer.write(head.encode("latin-1", "replace") + data)
            await writer.drain()
        except (ConnectionError, OSError):
            pass


async def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    allow = Allowlist(os.path.abspath(args.data))
    await allow.refresh()
    proxy = Proxy(allow)
    server = await asyncio.start_server(proxy.handle, args.host, args.port, limit=64 * 1024)
    log.info("listening on %s:%d", args.host, args.port)
    asyncio.create_task(allow.watch())
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
