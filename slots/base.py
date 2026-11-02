"""The slot contract.

Every piece of rotating content implements this. One slot is one module: a
`Slot` subclass, its `fetch()`, and its `fixture()`. Adding one never edits
central code - the registry finds it.

The cardinal rule from CLAUDE.md is enforced here rather than left to
discipline: `safe_fetch()` swallows every exception a slot can raise and turns
it into `None`. A slot author cannot break the morning print by writing a bad
collector, only by returning bad content.

Three shapes, one interface:
  * local data      - moon phase. No network, deterministic, never fails.
  * narrator text   - wise saying. Supplies a brief; the persona writes the copy.
  * image           - tarot. Produces a pre-dithered bitmap plus a brief.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as Date
from typing import Any, Literal

from PIL import Image

Tier = Literal["spine", "common", "uncommon", "rare", "legendary", "occasional"]


@dataclass(frozen=True)
class SlotSpec:
    """Static facts about a slot. Must agree with docs/SLOTS.md."""

    id: int
    name: str
    tier: Tier
    paper_mm: int
    needs_network: bool = False
    needs_narrator: bool = False
    # Declares that this slot's content has to be looked up on the live web.
    # The narrator attaches Anthropic's server-side web search to the single
    # daily call when any drawn slot asks for it (SYSTEM.md 10.2), so a search
    # slot still costs no extra round trip.
    needs_search: bool = False
    series: bool = False


@dataclass
class SlotResult:
    """What a slot contributes to the page.

    `head` is a *fallback* header. The persona renames it (SYSTEM.md 3.1) - a
    slot's own header text should never reach paper unrenamed.

    `brief` is handed to the narrator: the facts it may write around. Keep it
    small and factual. Anything in here can end up rephrased, so put nothing in
    it that must survive verbatim - that belongs in `body`.

    `answer` is the house rule for puzzles (SLOTS.md, PUZZLES): the solution
    prints the same day, upside-down at the footer. Nothing is ever carried over
    to tomorrow, because a receipt you have to keep is a receipt you have to
    file. Like `body` it is inserted as raw HTML, so a solved grid can be markup
    rather than text. The narrator never sees it and cannot rewrite it.

    `extra` is data the *page* needs and the narrator must never see: the
    weather's hourly series, which the persona's chosen layout draws from. It
    is not copy, it is not rephrasable, and putting it in `brief` would spend
    tokens on twenty-four numbers and invite the model to describe them.

    `fallback` says the body is a stand-in the narrator is expected to replace
    - a search slot's archived answer - and that `fine` describes the stand-in
    ("from the archive, 17 days old"). When the narrator writes a fresh body
    the fine goes with the old one; left behind, it labels today's finding as
    an old one.
    """

    head: str
    body: str | None = None
    image: Image.Image | None = None
    fine: str | None = None
    brief: dict[str, Any] = field(default_factory=dict)
    paper_mm: int | None = None
    answer: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    fallback: bool = False


@dataclass
class Context:
    """Everything a slot is allowed to know about today."""

    date: Date
    config: dict[str, Any] = field(default_factory=dict)
    store: Any = None          # data.store.Store, or None in tests
    offline: bool = False

    # Per-run scratch space, for work several slots would otherwise repeat.
    # The four weather slots share one Open-Meteo call through here rather than
    # making four. Keyed by whatever the sharer likes; nothing else reads it.
    shared: dict[str, Any] = field(default_factory=dict)

    def rng(self, slot_id: int) -> random.Random:
        """A generator seeded by (date, slot), so a day is reproducible.

        Two runs for the same date produce the same receipt. That is what makes
        `--date` useful for debugging and what stops a retry after a paper jam
        printing something different.
        """
        return random.Random(f"{self.date.isoformat()}:{slot_id}")


class Slot(ABC):
    """Base class. Subclasses set `spec` and implement `fetch` and `fixture`.

    A subclass declares the spec `docs/SLOTS.md` gives it. At registration the
    instance's `spec` is replaced with a configured one, and `base_spec` keeps
    the declared version - so tier and paper size are tunable from
    `config.toml` without the module or the docs having to change. Read `spec`
    everywhere; `base_spec` exists for the coverage report.
    """

    spec: SlotSpec
    base_spec: SlotSpec

    @abstractmethod
    def fetch(self, ctx: Context) -> SlotResult | None:
        """Produce today's content, or None to be dropped.

        May raise - `safe_fetch` handles it. Return None for "nothing to say
        today", which is not a failure (no ISS pass tonight, no photo matching
        this date).
        """

    @abstractmethod
    def fixture(self, ctx: Context) -> SlotResult:
        """A deterministic offline sample.

        Every slot ships one so the whole receipt renders with no network and no
        API key. This is what the contact sheet and the layout tests run on.
        """

    def after_narration(self, store: Any, day: Date, head: str,
                        body: str) -> None:
        """Called with what the narrator actually wrote, on a real morning only.

        Most slots have nothing to keep. The few that do are the ones whose
        content only exists once the narrator has written it: a search slot
        caching its finding as tomorrow's fallback, the running bit keeping the
        joke it invented so it can call it back in a month. Never called for a
        simulation or a dry run, so nothing a preview writes can become part of
        the machine's memory.
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} #{self.spec.id} {self.spec.name!r}>"


@dataclass
class SlotFailure:
    """A slot that raised. Kept so the persona can mourn it (SYSTEM.md 7)."""

    slot_id: int
    name: str
    error: str


def safe_fetch(slot: Slot, ctx: Context,
               failures: list[SlotFailure] | None = None) -> SlotResult | None:
    """Fetch a slot without letting it take the morning down.

    This is the only place slots should be called from. It is deliberately a
    bare `except Exception` - a slot reaching the network at 07:00 can fail in
    ways nobody enumerated, and a blank receipt is worse than a missing section.
    """
    try:
        result = slot.fixture(ctx) if ctx.offline else slot.fetch(ctx)
    except Exception as exc:  # noqa: BLE001 - deliberate, see docstring
        if failures is not None:
            failures.append(SlotFailure(slot.spec.id, slot.spec.name,
                                        f"{type(exc).__name__}: {exc}"))
        return None

    if result is not None and result.paper_mm is None:
        result.paper_mm = slot.spec.paper_mm
    return result
