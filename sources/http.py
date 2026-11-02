"""Shared HTTP fetching and last-known-good caching.

Every network source needs the same four things: a user agent, a timeout, JSON
decoding, and a cache that serves the previous good answer when the network is
down.

**The cache is the whole reason "network off still prints" is true.** A source
stores every success under a namespace, and serves the most recent stored
payload when a fetch fails. A day-old article is wrong about being today's and
right about everything else; a blank section is wrong about everything.

Nothing here raises into `main` - callers are slots, and `safe_fetch` catches
what gets past them. But a source that can serve *something* should, so
`cached_json` prefers a stale hit over an exception.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date as Date
from typing import Any

import config

TIMEOUT = 12
# Wikimedia in particular asks for a descriptive agent with contact information
# and rate-limits generic ones. Being identifiable is also just good manners for
# a script that hits public APIs unattended every morning. The contact is
# QG_CONTACT in .env.
UA = "quick-guthe/0.1 (personal receipt printer{})".format(
    f"; +{config.contact()}" if config.contact() else "")


class SourceUnavailable(RuntimeError):
    """No live fetch and nothing cached. The slot should drop."""


def get_bytes(url: str, *, accept: str | None = None,
              extra_headers: dict[str, str] | None = None) -> bytes:
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    headers.update(extra_headers or {})
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read()


def get_json(url: str, *, extra_headers: dict[str, str] | None = None) -> Any:
    return json.loads(get_bytes(url, accept="application/json",
                                extra_headers=extra_headers).decode("utf-8"))


def cached_json(url: str, *, store: Any, namespace: str, key: str,
                offline: bool = False, when: Date | None = None) -> tuple[Any, bool]:
    """(payload, stale). Live where possible, last-known-good where not.

    `stale` is returned rather than assumed so the slot can say so on paper.
    Reporting a cached answer as fresh is the one failure mode worse than
    dropping the section (SYSTEM.md 9).
    """
    if not offline:
        try:
            payload = get_json(url)
            if store is not None:
                store.put(namespace, key, payload, when=when or Date.today())
            return payload, False
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass                      # fall through to the cache

    if store is not None:
        exact = store.fetch(namespace, key)
        if exact is not None:
            return exact, offline is False
        latest = store.latest(namespace)
        if latest is not None:
            return latest[1], True

    raise SourceUnavailable(f"{namespace}: no live fetch and nothing cached")
