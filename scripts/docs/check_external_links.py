#!/usr/bin/env python3
"""Best-effort external link checker for README and docs.

Collects http(s) links from README.md and docs/**/*.md, then probes each one
with a short timeout and a couple of retries. This is intentionally **advisory**:
it always exits 0 so a transient outage or a site that blocks bots never makes CI
unusable. Wire it into a `continue-on-error` step for signal without a hard gate.

    python scripts/docs/check_external_links.py
"""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGETS = [REPO / "README.md", *sorted((REPO / "docs").rglob("*.md"))]

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\((https?://[^)\s]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]*`")

# Hosts that commonly rate-limit or block automated HEAD/GET requests. Links to
# these are collected but not failed on; skip probing to reduce noise.
ALLOWLIST_SKIP = {
    "img.shields.io",
    "en.wikipedia.org",
}

TIMEOUT = 8
RETRIES = 2
USER_AGENT = "forgeguard-docs-linkcheck/1.0"


def strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))


def collect_links() -> dict[str, list[Path]]:
    links: dict[str, list[Path]] = {}
    for path in TARGETS:
        if not path.exists():
            continue
        body = strip_code(path.read_text(encoding="utf-8"))
        for url in LINK_RE.findall(body):
            links.setdefault(url.rstrip("."), []).append(path)
    return links


def probe(url: str) -> tuple[bool, str]:
    last = ""
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(
                url, method="HEAD", headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return True, str(resp.status)
        except urllib.error.HTTPError as e:
            # Some servers reject HEAD; retry once with GET.
            if e.code in (403, 405):
                try:
                    req = urllib.request.Request(
                        url, method="GET", headers={"User-Agent": USER_AGENT}
                    )
                    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                        return True, str(resp.status)
                except Exception as ge:  # noqa: BLE001
                    last = f"{type(ge).__name__}"
            else:
                last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001 - advisory tool
            last = type(e).__name__
        if attempt < RETRIES:
            time.sleep(1 + attempt)
    return False, last


def main() -> int:
    links = collect_links()
    if not links:
        print("No external links found.")
        return 0

    failures: list[tuple[str, str]] = []
    skipped = 0
    for url in sorted(links):
        host = urllib.request.urlparse(url).hostname or ""
        if host in ALLOWLIST_SKIP:
            skipped += 1
            continue
        ok, info = probe(url)
        if not ok:
            failures.append((url, info))
            print(f"WARN  unreachable ({info}): {url}")

    print(
        f"\nChecked {len(links) - skipped} external links "
        f"({skipped} skipped by allowlist) · {len(failures)} unreachable"
    )
    # Advisory only: never fail the build.
    return 0


if __name__ == "__main__":
    sys.exit(main())
