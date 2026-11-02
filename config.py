"""Configuration loading.

One source of truth for every tunable, read from `config.toml`. Nothing in the
codebase should hardcode a weight, a threshold, a path or a coordinate.
"""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from datetime import date as Date
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.toml"
LOCAL_PATH = ROOT / "config.local.toml"
ENV_PATH = ROOT / ".env"


@lru_cache(maxsize=1)
def load_env() -> None:
    """Read .env into the environment, without clobbering real env vars.

    `config.toml` is committed, so anything personal belongs in `.env` instead.
    Hand-parsed rather than adding a dependency for twelve lines.
    """
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def _merge(base: dict, over: dict) -> dict:
    """`over` laid on `base`: tables merge key by key, anything else replaces."""
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict[str, Any]:
    """`config.toml`, with `config.local.toml` merged over it when present.

    The local file is gitignored and holds personal tuning - your own news
    feeds above all. A list in it, such as `[[news.feeds]]`, replaces the
    committed list rather than extending it.
    """
    p = path or CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - copy config.toml from the repo")
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    if path is None and LOCAL_PATH.exists():
        data = _merge(data, tomllib.loads(LOCAL_PATH.read_text(encoding="utf-8")))
    return data


def get(*keys: str, default: Any = None) -> Any:
    """Dotted lookup: get('weather', 'day_start')."""
    node: Any = load()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def path(*keys: str) -> Path:
    """A configured path, resolved against the repo root."""
    value = get(*keys)
    if value is None:
        raise KeyError(f"no path configured at {'.'.join(keys)}")
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def reader_name() -> str:
    """Who the receipt is for: QG_NAME in .env, else `[reader] name`.

    Personas address the reader by name, and some print it - a share ticker, a
    playbill, a scoreboard.
    """
    load_env()
    name = os.environ.get("QG_NAME", "").strip()
    return name or str(get("reader", "name", default="Sam")).strip() or "Sam"


def contact() -> str:
    """A URL or address for the User-Agent, from QG_CONTACT in .env, or ""."""
    load_env()
    return os.environ.get("QG_CONTACT", "").strip()


def location() -> tuple[float, float, str]:
    """(latitude, longitude, display name).

    `.env` wins over `config.toml`, so the committed file can keep a harmless
    placeholder while the real coordinates stay out of git:

        QG_LATITUDE=51.5074
        QG_LONGITUDE=-0.1278
        QG_LOCATION_NAME=London
    """
    load_env()
    loc = get("location") or {}

    lat = os.environ.get("QG_LATITUDE", loc.get("latitude"))
    lon = os.environ.get("QG_LONGITUDE", loc.get("longitude"))
    name = os.environ.get("QG_LOCATION_NAME", loc.get("name", ""))

    if lat is None or lon is None:
        raise KeyError(
            "No location set. Put QG_LATITUDE / QG_LONGITUDE in .env "
            "(preferred - .env is gitignored) or [location] in config.toml.")
    return float(lat), float(lon), name


def city() -> str:
    """The city to look for things to do in, from QG_CITY in .env.

    Distinct from the location name, which is the place the weather is for: a
    suburb is the right answer to "will it rain here" and the wrong one to
    "what's on tonight". Falls back to the location name when unset.
    """
    load_env()
    name = os.environ.get("QG_CITY", "").strip()
    if name:
        return name
    try:
        return location()[2]
    except KeyError:
        return ""


def location_is_placeholder() -> bool:
    """True while the committed London placeholder is still in force."""
    load_env()
    if "QG_LATITUDE" in os.environ:
        return False
    loc = get("location") or {}
    return (round(float(loc.get("latitude", 0)), 2),
            round(float(loc.get("longitude", 0)), 2)) == (51.51, -0.13)


def friend_timezones() -> list[str]:
    """Friends' IANA zone names from TIMEZONES in .env, comma-separated.

        TIMEZONES=America/New_York,Asia/Tokyo,Australia/Sydney

    Order kept, blanks and repeats dropped. Validity is not checked here: a zone
    the tz database does not know is dropped by slot 72 on its own, so a typo
    costs one friend rather than the section.
    """
    load_env()
    zones: list[str] = []
    for part in os.environ.get("TIMEZONES", "").split(","):
        zone = part.strip()
        if zone and zone not in zones:
            zones.append(zone)
    return zones


def birth_date() -> Date | None:
    """The full date of birth from QG_BIRTHDAY in .env, as DD-MM-YYYY.

    The format is enforced rather than guessed: 03-04-2000 is a different
    birthday depending on which convention you assume, and a wrong guess prints
    the birthday section a month early. Malformed input returns None rather
    than raising, so a typo in .env cannot stop the morning print.
    """
    load_env()
    raw = os.environ.get("QG_BIRTHDAY", "").strip()
    try:
        day, month, year = (int(part) for part in raw.split("-"))
        if year < 1900:
            return None
        return Date(year, month, day)
    except (ValueError, TypeError):
        return None


def birthday() -> tuple[int, int] | None:
    """(month, day) of the birthday, for recurring checks. None if unset."""
    born = birth_date()
    return (born.month, born.day) if born else None
