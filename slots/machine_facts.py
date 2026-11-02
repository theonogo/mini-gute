"""Slot 46 - Machine facts.

One true fact about the printer, the paper, or the code that made the receipt.
Deadpan and self-referential.

**Every fact is computed, not written down.** SLOTS.md is explicit that facts
must be true of the machine currently attached: a printer swap takes the old
width and speed figures with it. Any number here is read from `printer.base`, the font manifest, the registry
or the store at the moment the receipt is composed, so a fact cannot rot. The
only hardcoded numbers are the ones printed on the TM-T20II's own datasheet.

**Never about how much paper is left**, per the spec. The machine does not know
and guessing would be the one fact on the receipt that is not true.

The fact is verbatim. A persona restating "576 dots" in its own words is one
paraphrase away from being wrong, and SYSTEM.md 9 puts facts outside the voice.
The header carries the persona instead.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# From the TM-T20II datasheet, not from the running code, because nothing in
# the process can observe them. They are the one thing here to re-check if the
# printer is ever swapped again.
PRINT_SPEED_MM_S = 200
PAPER_WIDTH_MM = 80


def facts(ctx: Context) -> list[str]:
    """Every fact, each one true at the moment it is generated."""
    from printer.base import DOTS_PER_MM, WIDTH_DOTS
    from render.fonts import manifest
    from render.page import DEFAULT_THRESHOLD

    faces = sum(len(v) for v in manifest().values())
    out = [
        "Thermal paper carries no ink. The paper itself darkens under heat, "
        "which is why this receipt will fade if you leave it in the sun.",

        f"This page is {WIDTH_DOTS} dots wide. At {DOTS_PER_MM} dots per "
        f"millimetre that is {WIDTH_DOTS // DOTS_PER_MM}mm of print on an "
        f"{PAPER_WIDTH_MM}mm roll. The rest is margin, and unprintable.",

        f"{WIDTH_DOTS} is divisible by eight. It has to be: each row of dots is "
        f"packed into whole bytes, and a width that is not a multiple of eight "
        f"prints as a diagonal smear rather than as an error.",

        "This receipt was composed as a web page, photographed by a browser "
        "with no screen, and reduced to pure black and white. There are no "
        "greys anywhere on it.",

        f"Every grey was decided by one number: anything darker than "
        f"{DEFAULT_THRESHOLD} of 255 became black, everything lighter became "
        f"white. That number was chosen by printing a test card and looking at "
        f"it.",

        f"The head prints at about {PRINT_SPEED_MM_S}mm per second, so this "
        f"receipt took roughly as long to print as it takes to read one line "
        f"of it.",

        f"{faces} font files are embedded in this page as text, because a font "
        f"loaded from a web address would silently fail at seven in the morning "
        f"and nobody would know until the receipt looked wrong.",

        "The cutter is a partial cut. It leaves a small tab of paper joining "
        "this receipt to the next one, so the roll never loses its place.",

        "Nothing on this page is a font the printer knows about. Every "
        "character, rule and barcode arrived as pixels.",
    ]

    registry = _registry_fact()
    if registry:
        out.append(registry)
    archive = _archive_fact(ctx)
    if archive:
        out.append(archive)
    return out


def _registry_fact() -> str | None:
    try:
        from .registry import coverage
        cov = coverage()
    except Exception:  # noqa: BLE001 - a fact that cannot be checked is dropped
        return None
    return (f"{len(cov.built)} of {cov.total} possible sections have been "
            f"built. The rest do not exist yet, and this is one of the ones "
            f"that does.")


def _archive_fact(ctx: Context) -> str | None:
    """Only offered once there is an archive worth mentioning."""
    store = getattr(ctx, "store", None)
    if store is None:
        return None
    try:
        count = store.receipt_count()
    except Exception:  # noqa: BLE001
        return None
    if count < 10:
        return None
    return (f"{count} receipts have been printed and recorded. The machine "
            f"remembers all of them, which is more than can be said for the "
            f"mornings.")


@register
class MachineFacts(Slot):
    spec = SlotSpec(id=46, name="Machine facts", tier="uncommon",
                    paper_mm=26, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        pool = facts(ctx)
        return SlotResult(
            head="Machine Facts",
            body=ctx.rng(self.spec.id).choice(pool),
            brief={"verbatim": True,
                   "subject": "this printer and the code that drives it",
                   "instruction": "Name this section in voice. The fact is "
                                  "measured and prints unaltered."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
