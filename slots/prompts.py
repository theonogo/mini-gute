"""Slots 12, 66, 73 and 141 - the receipt asking for something back.

Each prints a QR that opens a pre-addressed, pre-titled email, so replying costs
a tap and a sentence (SYSTEM.md 6.1). What comes back is read by
`sources/mailbox.py` and printed by the slots in `inbox.py`, or - for feedback -
handed to the persona to argue with.

**A question about a real morning, not a rating.** Feedback names a section that
actually printed, on the day it printed, because "how was your receipt?" gets
nothing and "was Tuesday's nonogram beneath you?" gets an answer. The archive
supplies the fact; the persona supplies the asking. With nothing in the archive
there is nothing to ask about, and the section drops.

**Replies are story, not telemetry.** SYSTEM.md 6.3: three uncommon slots yield
about four signals a month, far too sparse to tune weights with. So a reply is
printed back to be answered, and the weights stay hand-tuned.
"""

from __future__ import annotations

import math

import config
from sources import mailbox

from .base import Context, Slot, SlotResult, SlotSpec
from .inbox import _CSS, _escape, qr_block
from .registry import register

# Photograph assignments. Deliberately about attention rather than photography:
# every one of these can be done on the way to somewhere else.
ASSIGNMENTS = [
    "Photograph something red today.",
    "Photograph a door you have never opened.",
    "Photograph the oldest thing you touch today.",
    "Photograph something that is repaired rather than replaced.",
    "Photograph a queue.",
    "Photograph something growing where it should not be.",
    "Photograph the view from a window that is not yours.",
    "Photograph a handwritten sign.",
    "Photograph something you walk past every day and have never looked at.",
    "Photograph a reflection that is better than the thing.",
    "Photograph the smallest animal you see.",
    "Photograph something that will be gone within a week.",
    "Photograph a colour you cannot name.",
    "Photograph the back of a building whose front you know.",
    "Photograph something left behind on purpose.",
]

# Slot 73: how far the dead drop can be, in metres. Near enough to walk to,
# far enough not to be the corner shop.
DROP_MIN_M = 500
DROP_MAX_M = 2_000
EARTH_R = 6_371_000


def drop_point(lat: float, lon: float, rng) -> tuple[float, float, int]:
    """A point at a random bearing and distance from home. (lat, lon, metres)."""
    metres = rng.randint(DROP_MIN_M, DROP_MAX_M)
    bearing = math.radians(rng.uniform(0, 360))
    angular = metres / EARTH_R
    lat1, lon1 = math.radians(lat), math.radians(lon)
    lat2 = math.asin(math.sin(lat1) * math.cos(angular)
                     + math.cos(lat1) * math.sin(angular) * math.cos(bearing))
    lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(angular) * math.cos(lat1),
                             math.cos(angular) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2), metres


@register
class PromptedFeedback(Slot):
    """12 - the persona asks about one section of one real morning."""

    spec = SlotSpec(id=12, name="Prompted feedback QR", tier="uncommon",
                    paper_mm=45, needs_network=True, needs_narrator=True)

    def _subject(self, ctx: Context) -> tuple[str, str] | None:
        """(section name, when) from a real receipt, or None with no archive."""
        from data.archive import is_rotating, name, receipts
        rows = receipts(ctx.store, 14)
        rng = ctx.rng(self.spec.id)
        candidates = [(int(s), row["day"]) for row in rows
                      for s in row.get("slots", []) if is_rotating(int(s))]
        if not candidates:
            return None
        sid, day = rng.choice(candidates)
        from datetime import date as Date
        when = Date.fromisoformat(day)
        ago = (ctx.date - when).days
        if ago <= 1:
            phrase = "yesterday's" if ago == 1 else "this morning's"
        elif ago <= 7:
            phrase = f"{when:%A}'s"
        else:
            phrase = f"the {when:%d %B}"
        return name(sid), phrase

    def fetch(self, ctx: Context) -> SlotResult | None:
        if not mailbox.configured():
            return None
        subject = self._subject(ctx)
        if subject is None:
            return None                       # no archive, nothing to ask about
        section, when = subject

        # An unanswered reply is handed to the persona to respond to, which is
        # what feedback is for here (SYSTEM.md 6.3) - and marked used, so it is
        # answered once and not brought up every morning afterwards.
        answered = mailbox.unused(ctx, "FEEDBACK")
        reply = answered[-1] if answered else None
        if reply is not None:
            mailbox.mark_used(ctx, reply.uid)

        # The question is the body, so the persona writes it: this is the one
        # slot whose whole point is being asked something in voice. The QR
        # therefore lives in `fine`, which the narrator has no field for - a
        # body it can write into is a body it could replace the code with.
        asked = f"{when} {section.lower()}"
        fallback = f"Was {asked} any good? One line, honestly."
        return SlotResult(
            head="A Question",
            body=fallback,
            fine=(_CSS + qr_block("FEEDBACK", "Reply in one line. It will be "
                                              "read out, and argued with.")),
            brief={"asked_about": asked,
                   "previous_reply": reply.body[:300] if reply else None,
                   "instruction": "Write ONE question, in voice, asking "
                                  f"{config.reader_name()} something specific "
                                  f"about {asked} - whether "
                                  "it was any good, too easy, worth the paper. "
                                  "If a previous reply is given, respond to it "
                                  "first in one short line: agree, argue, take "
                                  "offence, whatever suits you. Never invent "
                                  "what the reply said, and ask only about the "
                                  "section named.",
                   },
        )

    def fixture(self, ctx: Context) -> SlotResult | None:
        return None


@register
class PhotoAssignment(Slot):
    """66 - an assignment today, a printed photograph some morning later."""

    spec = SlotSpec(id=66, name="Photo assignment QR", tier="uncommon",
                    paper_mm=46, needs_network=True, needs_narrator=True)

    def _result(self, assignment: str) -> SlotResult:
        return SlotResult(
            head="Assignment",
            body=(f'{_CSS}<div class="mail-body">{_escape(assignment)}</div>'
                  + qr_block("PHOTO", "Attach the photograph. It comes back as "
                                      "a printed picture, some morning.")),
            brief={"verbatim": True, "assignment": assignment,
                   "instruction": "Name this section in voice and add at most "
                                  "one line of encouragement or threat. The "
                                  "assignment itself prints as written."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        if not mailbox.configured():
            return None
        recent: list[str] = []
        if ctx.store is not None:
            try:
                recent = list(ctx.store.fetch("photo", "recent", []) or [])
            except Exception:  # noqa: BLE001
                recent = []
        pool = [a for a in ASSIGNMENTS if a not in recent] or ASSIGNMENTS
        assignment = ctx.rng(self.spec.id).choice(pool)
        if ctx.store is not None and ctx.shared.get("real_morning"):
            try:
                ctx.store.put("photo", "recent", ([assignment] + recent)[:8])
            except Exception:  # noqa: BLE001
                pass
        return self._result(assignment)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ASSIGNMENTS[0])


@register
class DeadDrop(Slot):
    """73 - coordinates within walking distance. Go there, photograph it.

    *Deviation from the catalogue:* SLOTS.md files this as "a variant of 66"
    with no tier of its own. It is registered as an uncommon slot in its own
    right, because it is drawn, costed and suppressed separately - a variant
    that shares 66's draw would print two assignments on one morning.
    """

    spec = SlotSpec(id=73, name="Dead drop", tier="uncommon", paper_mm=47,
                    needs_narrator=True)

    def _result(self, lat: float, lon: float, metres: int) -> SlotResult:
        from render.dither import img_tag
        from render.qr import qr_image
        # A geo: URI opens the phone's map on the point. The coordinates are
        # printed as well, because a code that fails to scan in a kitchen
        # should not cost the whole section.
        code = img_tag(qr_image(f"geo:{lat:.5f},{lon:.5f}"))
        return SlotResult(
            head="Dead Drop",
            body=(f'{_CSS}<div class="drop-coords">{lat:.5f}<br>{lon:.5f}</div>'
                  f'<div class="qr-block">{code}'
                  f'<div class="qr-cap">About {metres:,}m away. Go and '
                  f'photograph whatever is there.</div></div>'
                  '<style>.drop-coords { font-family: var(--font-mono);'
                  ' font-size: calc(var(--size-body) + 8px); text-align: center;'
                  ' line-height: 1.15; letter-spacing: .04em; }</style>'),
            fine=f"Send it to {mailbox.address()} with PHOTO in the subject."
                 if mailbox.configured() else None,
            brief={"verbatim": True, "metres_away": metres,
                   "instruction": "Name this section in voice and add at most "
                                  "one line. The coordinates print as they are "
                                  "and are not yours to change or describe - "
                                  "you do not know what is there either."},
        )

    def _point(self, ctx: Context):
        lat, lon, _ = config.location()
        return drop_point(lat, lon, ctx.rng(self.spec.id))

    def fetch(self, ctx: Context) -> SlotResult | None:
        try:
            return self._result(*self._point(ctx))
        except KeyError:                      # no location configured
            return None

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self.fetch(ctx)


@register
class SlotSuggestion(Slot):
    """141 - the machine proposes a section it thinks should exist."""

    spec = SlotSpec(id=141, name="New slot suggestion", tier="rare",
                    paper_mm=45, needs_network=True, needs_narrator=True)

    FALLBACK = ("A section that prints the one thing you looked up yesterday "
                "and have already forgotten.")

    def _proposal(self, ctx: Context) -> str | None:
        if ctx.offline or not ctx.shared.get("may_narrate", True):
            return None
        import narrator
        from .registry import all_slots
        existing = ", ".join(sorted(s.spec.name for s in all_slots()))
        persona = None
        try:
            import main
            persona = main.load_personas(auditions=True).get(
                ctx.shared.get("persona_name", ""))
        except Exception:  # noqa: BLE001 - voiceless is still a proposal
            persona = None
        return narrator.freeform(
            ctx.date, persona,
            "Propose ONE new section this receipt printer should print every so "
            "often, in voice. Two sentences: what it is, and why it is worth "
            "the paper. It must be printable on a 72mm thermal till roll with "
            "no screen and no colour. Do not propose anything already in this "
            "list: " + existing,
            max_words=60)

    def fetch(self, ctx: Context) -> SlotResult | None:
        if not mailbox.configured():
            return None
        proposal = self._proposal(ctx) or self.FALLBACK
        if ctx.store is not None and ctx.shared.get("real_morning"):
            try:
                past = list(ctx.store.fetch("suggestion", "proposed", []) or [])
                ctx.store.put("suggestion", "proposed",
                              (past + [{"day": ctx.date.isoformat(),
                                        "text": proposal}])[-40:])
            except Exception:  # noqa: BLE001
                pass
        verdicts = mailbox.unused(ctx, "IDEA")
        said = ""
        if verdicts:
            verdict = verdicts[-1]
            mailbox.mark_used(ctx, verdict.uid)
            said = (f'<div class="mail-from">your verdict</div>'
                    f'<div class="mail-body mail-quote">'
                    f'{_escape(verdict.body)}</div>')
        return SlotResult(
            head="Proposal",
            body=(f'{_CSS}{said}<div class="mail-body">{_escape(proposal)}</div>'
                  + qr_block("IDEA", "Yes, no, or what it should be instead.")),
            brief={"verbatim": True, "proposal": proposal,
                   "instruction": "Name this section in voice. The proposal "
                                  "prints as written - it is already in your "
                                  "words. Add nothing to it."},
        )

    def fixture(self, ctx: Context) -> SlotResult | None:
        return None
