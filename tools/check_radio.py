#!/usr/bin/env python3
"""Check live radio streams sequentially and persist their successful probe counts."""

import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
PLS_LIMIT = 64 * 1024


def stations(doc):
    for lang in doc["languages"].values():
        for genre in lang["genres"].values():
            yield from genre["stations"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value, indent=None):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        temp_path = Path(output.name)
        try:
            os.fchmod(output.fileno(), mode)
            json.dump(value, output, ensure_ascii=False, indent=indent)
            output.flush()
            os.fsync(output.fileno())
            os.replace(temp_path, path)
            dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            temp_path.unlink(missing_ok=True)


def pls_targets(url, deadline):
    with urlopen(url, timeout=deadline - time.monotonic()) as response:
        base = response.geturl()
        body = bytearray()
        while len(body) <= PLS_LIMIT and time.monotonic() < deadline:
            chunk = response.read1(min(4096, PLS_LIMIT + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if len(body) > PLS_LIMIT or time.monotonic() >= deadline:
            return ()
    lines = body.decode("utf-8-sig", errors="replace").splitlines()
    if not lines or lines[0].strip().lower() != "[playlist]":
        return (url,)
    entries = (
        re.fullmatch(r"\s*File\d+\s*=\s*(\S+)\s*", line, re.I)
        for line in lines[1:]
    )
    return tuple(dict.fromkeys(urljoin(base, entry[1]) for entry in entries if entry))


def probe(url, timeout):
    deadline = time.monotonic() + timeout
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            return False
        targets = (url,)
        if parts.path.lower().endswith((".pls", "/pls")):
            targets = pls_targets(url, deadline)
    except (OSError, ValueError, http.client.HTTPException):
        return False

    for target in targets:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if probe_audio(target, remaining):
            return True
    return False


def probe_audio(url, timeout):
    try:
        if urlsplit(url).scheme not in {"http", "https"}:
            return False
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-protocol_whitelist", "http,https,tcp,tls,crypto",
                "-rw_timeout", str(int(timeout * 1_000_000)),
                "-probesize", "65536", "-analyzeduration", "2000000",
                "-select_streams", "a:0", "-read_intervals", "%+#1",
                "-show_entries", "packet=stream_index", "-of", "csv=p=0",
                "-i", url,
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False,
        )
    except (ValueError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and any(
        line.partition(b",")[0].isdigit() for line in result.stdout.splitlines()
    )


def flush_counts(path, doc, rows, state, state_path):
    pending = state.get("pending")
    if not pending:
        return
    changed = False
    for offset, count in pending.items():
        row = rows[int(offset)]
        if row["active"] == count - 1:
            row["active"] = count
            changed = True
        elif row["active"] != count:
            raise SystemExit(f"{path.name} active count changed. Review the checkpoint.")
    if changed:
        write_json(path, doc, indent=1)
    del state["pending"]
    write_json(state_path, state)


def run(args, state_path):
    radio_dir = args.data_dir / "radio"
    files = sorted(radio_dir.glob("*.json"), key=lambda p: (p.stem != "south_korea", p.name))
    if not files:
        raise SystemExit(f"No radio files in {radio_dir}")
    names = [path.name for path in files]
    state = read_json(state_path) if state_path.exists() else {
        "round": 1, "files": names, "file_index": 0, "offset": 0,
        "checked": 0, "passed": 0,
    }
    finished_at = state.get("finished_at")
    if finished_at is not None:
        if not args.repeat:
            print(f"Round {state['round']} already completed. Use --repeat for further checks.")
            return
        time.sleep(max(0, finished_at + args.round_delay - time.time()))
        state = {
            "round": state["round"] + 1, "files": names, "file_index": 0, "offset": 0,
            "checked": 0, "passed": 0,
        }
        write_json(state_path, state)

    if state["files"] != names:
        raise SystemExit("Country files changed during the current round. Review the checkpoint.")

    attempts = 0
    for file_index in range(state["file_index"], len(files)):
        path = files[file_index]
        doc = read_json(path)
        rows = list(stations(doc))
        flush_interval = 1 if len(rows) < 5_000 else 100
        signature = hashlib.sha256(
            json.dumps([row["url"] for row in rows]).encode()
        ).hexdigest()
        if state.get("signature", signature) != signature:
            raise SystemExit(f"{path.name} station URLs changed. Review the checkpoint.")
        state["signature"] = signature

        flush_counts(path, doc, rows, state, state_path)
        # These offsets were already probed out of order in this country and round.
        priority_checked = set(state.get("priority_checked", ()))
        for offset in range(state["offset"], len(rows)):
            if offset in priority_checked:
                continue
            if attempts == args.limit:
                flush_counts(path, doc, rows, state, state_path)
                return
            row = rows[offset]
            time.sleep(args.delay)
            passed = probe(row["url"], args.timeout)
            attempts += 1
            if passed:
                state.setdefault("pending", {})[str(offset)] = row["active"] + 1
                state["passed"] += 1
            state["checked"] += 1
            state["offset"] = offset + 1
            write_json(state_path, state)
            if offset < 5 or state["offset"] % flush_interval == 0:
                flush_counts(path, doc, rows, state, state_path)
            if state["checked"] <= 5 or state["checked"] % 100 == 0:
                print(f"Round {state['round']} | {state['checked']} checked | "
                      f"{state['passed']} active | {path.stem}", flush=True)

        flush_counts(path, doc, rows, state, state_path)
        state["file_index"] = file_index + 1
        state["offset"] = 0
        del state["signature"]
        state.pop("priority_checked", None)
        write_json(state_path, state)
    state["finished_at"] = time.time()
    write_json(state_path, state)
    print(f"Round {state['round']} complete | {state['checked']} checked | "
          f"{state['passed']} active", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--delay", type=int, default=10, help="Seconds between probes (minimum 10)")
    parser.add_argument("--timeout", type=int, default=12, help="Maximum seconds per probe")
    parser.add_argument("--limit", type=int, help="Stop after this many new probes")
    parser.add_argument("--repeat", action="store_true", help="Repeat completed rounds")
    parser.add_argument("--round-delay", type=int, default=7 * 86400,
                        help="Seconds to wait after a complete round")
    args = parser.parse_args()
    if args.delay < 10 or args.timeout < 1 or args.round_delay < 10:
        parser.error("Minimum delay, timeout and round delay are 10, 1 and 10 seconds")
    if args.limit is not None and (args.limit < 1 or args.repeat):
        parser.error("--limit must be positive and cannot be combined with --repeat")
    if not shutil.which("ffprobe"):
        parser.error("ffprobe is required (install FFmpeg)")
    if not (args.data_dir / "radio").is_dir():
        parser.error("data directory must contain radio/")
    state_dir = args.data_dir / ".radio-check"
    state_dir.mkdir(exist_ok=True)
    with (state_dir / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("A check is already running for this data directory")
        while True:
            run(args, state_dir / "progress.json")
            if not args.repeat:
                break


if __name__ == "__main__":
    main()
