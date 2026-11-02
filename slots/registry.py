"""Slot registry, tuning overrides and coverage reporting.

Slots self-register with `@register`, so adding one is a single new file. The
registry is also the project's progress bar: `coverage()` diffs what is built
against what `docs/SLOTS.md` promises, which is the only honest answer to "how
much of this is left".

**Tier and paper size are tunable from `config.toml`, not from the code.**
A slot module declares the tier `docs/SLOTS.md` specifies, and `[slots.tier]`
in the config overrides it. Rarity is the knob most likely to be wrong on first
contact with real mornings - the doc's guess at what feels rare is a guess - so
changing it should cost a config edit rather than a code edit and a commit. The
same applies to `paper_mm`, and `disabled` retires a slot without deleting it.

Two specs per slot, which is what makes this honest:

  * `slot.base_spec` - as built, matching `docs/SLOTS.md`. Coverage diffs this,
    so retuning a tier never shows up as the code drifting from the docs.
  * `slot.spec` - as configured. Everything at run time uses this one.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass, replace
from pathlib import Path

from .base import Slot, SlotSpec

_REGISTRY: dict[int, Slot] = {}

SLOTS_MD = Path(__file__).resolve().parent.parent / "docs" / "SLOTS.md"

# Matches the entry format documented at the top of SLOTS.md:
#   **37 · Moon phase** — common · 15mm · local calculation
_ENTRY = re.compile(
    r"^\*\*(?P<ids>\d+(?:\s*\+\s*\d+)*)\s*·\s*(?P<name>.+?)\*\*\s*"
    r"—\s*(?P<tier>[^·\n]+?)\s*(?:·|$)",
    re.M,
)


VALID_TIERS = {"spine", "common", "uncommon", "rare", "legendary", "occasional"}


def _tuning(sid: int) -> dict:
    """Config overrides for one slot, from `[slots.*]` in config.toml.

    Missing config is not an error - the registry has to work in tests and in
    tools that never load a config file, and a slot's built-in spec is always a
    valid answer.
    """
    try:
        import config
    except ImportError:                      # pragma: no cover - defensive
        return {}
    try:
        config.load()
    except FileNotFoundError:
        return {}

    key = str(sid)
    out: dict = {}
    tier = config.get("slots", "tier", key)
    if tier is not None:
        tier = str(tier).strip().lower()
        if tier not in VALID_TIERS:
            raise ValueError(
                f"config.toml [slots.tier] sets slot {sid} to {tier!r}, which is "
                f"not a tier. Valid: {', '.join(sorted(VALID_TIERS))}.")
        out["tier"] = tier
    paper = config.get("slots", "paper_mm", key)
    if paper is not None:
        out["paper_mm"] = int(paper)
    return out


def disabled_ids() -> set[int]:
    """Slots switched off in config. Retirement without deletion."""
    try:
        import config
        config.load()
    except (ImportError, FileNotFoundError):
        return set()
    return {int(x) for x in (config.get("slots", "disabled", default=[]) or [])}


def register(cls: type[Slot]) -> type[Slot]:
    """Class decorator. Registers one configured instance of the slot.

    The class keeps the spec it was written with; the instance gets the tuned
    one. Everything at run time reads `instance.spec`, so a tier changed in
    `config.toml` takes effect everywhere - selection, pricing and the
    itemization - without the module knowing it happened.
    """
    instance = cls()
    base: SlotSpec = instance.spec
    sid = base.id
    if sid in _REGISTRY:
        raise ValueError(
            f"slot id {sid} already registered by {_REGISTRY[sid]!r}. "
            f"IDs are stable and come from docs/SLOTS.md - never reuse one.")

    instance.base_spec = base
    tuned = _tuning(sid)
    if tuned:
        instance.spec = replace(base, **tuned)

    _REGISTRY[sid] = instance
    return cls


def load_all() -> None:
    """Import every module in this package so its slots register."""
    package = importlib.import_module(__package__)
    for mod in pkgutil.iter_modules(package.__path__):
        if mod.name in ("base", "registry"):
            continue
        importlib.import_module(f"{__package__}.{mod.name}")


def get(slot_id: int) -> Slot:
    return _REGISTRY[slot_id]


def every_slot() -> list[Slot]:
    """Every registered slot, including ones disabled in config."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def all_slots() -> list[Slot]:
    """Every slot that may print today. This is what the pipeline uses."""
    off = disabled_ids()
    return [s for s in every_slot() if s.spec.id not in off]


@dataclass
class DocEntry:
    id: int
    name: str
    tier: str


def documented() -> dict[int, DocEntry]:
    """Every slot promised by docs/SLOTS.md, excluding the CUT table."""
    text = SLOTS_MD.read_text(encoding="utf-8").split("## CUT")[0]
    out: dict[int, DocEntry] = {}
    for m in _ENTRY.finditer(text):
        tier = m.group("tier").strip().lower()
        # "rare to start, common while running" -> "rare"
        tier = tier.split(" to ")[0].split(",")[0].strip()
        for raw in re.findall(r"\d+", m.group("ids")):
            out[int(raw)] = DocEntry(int(raw), m.group("name").strip(), tier)
    return out


@dataclass
class Coverage:
    built: list[int]
    missing: list[DocEntry]
    undocumented: list[int]
    mismatched: list[tuple[int, str, str]]   # id, doc tier, code tier
    retuned: list[tuple[int, str, str]]      # id, built tier, configured tier
    disabled: list[int]

    @property
    def total(self) -> int:
        return len(self.built) + len(self.missing)

    @property
    def pct(self) -> float:
        return 100.0 * len(self.built) / max(1, self.total)


def coverage() -> Coverage:
    """Diff the registry against docs/SLOTS.md.

    Compares the spec each slot was *built* with, not the configured one. A tier
    deliberately retuned in `config.toml` is a tuning decision, not the code
    drifting from the docs, and reporting it as a mismatch would train everyone
    to ignore the mismatch list. Retunings are listed separately.
    """
    docs = documented()
    built = {s.spec.id: s for s in every_slot()}

    def as_built(slot: Slot) -> SlotSpec:
        return getattr(slot, "base_spec", slot.spec)

    mismatched = [
        (sid, docs[sid].tier, as_built(built[sid]).tier)
        for sid in sorted(set(docs) & set(built))
        if docs[sid].tier != as_built(built[sid]).tier
    ]
    retuned = [
        (sid, as_built(built[sid]).tier, built[sid].spec.tier)
        for sid in sorted(built)
        if as_built(built[sid]).tier != built[sid].spec.tier
    ]
    return Coverage(
        built=sorted(built),
        missing=[docs[i] for i in sorted(set(docs) - set(built))],
        undocumented=sorted(set(built) - set(docs)),
        mismatched=mismatched,
        retuned=retuned,
        disabled=sorted(disabled_ids() & set(built)),
    )
