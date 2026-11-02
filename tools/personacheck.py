"""Check every persona in `personas.toml` against what the machine expects.

The persona file is the one place where a typo is silent: a `[persona.blocks]`
key nobody reads, a masthead field with no fallback, a `variant_briefs` list
that is shorter than `variants`, a theme or a font that does not exist. None of
it raises - the morning just quietly prints something plainer than intended.

This is the ratification pass. It reads the file the way `main.py` does and
reports, per persona: the theme, the faces, the narrated masthead lines, the
blocks whose shape the persona bends (the coupon above all), and anything that
would not reach paper.

    python tools/personacheck.py            # every persona
    python tools/personacheck.py oracle     # just these
    python tools/personacheck.py --coupons  # the coupon column, in full
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from render.fonts import manifest  # noqa: E402
from slots.registry import all_slots, load_all  # noqa: E402

THEMES = main.PERSONAS / "themes"
VOCAB_KEYS = set(main.VOCAB_SLOTS)
BLOCK_KEYS = set(main.BLOCK_SLOTS)


def check(persona: dict) -> tuple[list[str], list[str]]:
    """(problems, notes) for one persona."""
    bad: list[str] = []
    notes: list[str] = []
    name = persona["name"]

    theme = THEMES / persona.get("theme", "")
    if not persona.get("theme"):
        bad.append("no theme file named")
    elif not theme.exists():
        (notes if persona.get("audition") else bad).append(
            f"theme {persona['theme']} missing"
            + (" (audition: falls back to _audition.css)" if persona.get("audition") else ""))

    faces = [persona.get("font")] + list(persona.get("fonts", {}).values())
    for face in faces:
        if isinstance(face, str) and face not in manifest():
            bad.append(f"font {face!r} is not in the manifest")

    for key in persona.get("vocabulary", {}):
        if key not in VOCAB_KEYS:
            bad.append(f"vocabulary key {key!r} belongs to no slot")
    for key, raw in (persona.get("blocks") or {}).items():
        if key not in BLOCK_KEYS:
            bad.append(f"blocks key {key!r} belongs to no slot")
        bad += check_block(key, main.block_spec(raw), notes)

    # Absorption ([persona.absorbs]): <slot id> = <masthead field>. Both halves
    # are silent when wrong - an id that belongs to no slot simply never fires,
    # and a field that does not exist eats the slot's section without printing
    # anything in its place, which is the worst failure on this list.
    slots_by_id = {s.spec.id for s in all_slots()}
    for sid, key in (persona.get("absorbs") or {}).items():
        if not str(sid).isdigit() or int(sid) not in slots_by_id:
            bad.append(f"absorbs: {sid} is not a slot id")
        if key not in (persona.get("masthead") or {}):
            bad.append(f"absorbs: {sid} feeds masthead.{key}, which is not declared")
        elif "absorbed" not in (persona["masthead"][key]):
            notes.append(f"absorbs: masthead.{key} has no `absorbed` table, so it "
                         "prints at its ordinary length on the day it eats a slot")

    variants = int(persona.get("variants", 1))
    briefs = persona.get("variant_briefs")
    if briefs is not None and len(briefs) != variants:
        bad.append(f"{len(briefs)} variant_briefs for {variants} variants")

    lengths = []
    for key, field in (persona.get("masthead") or {}).items():
        for name, over in (("absorbed", field.get("absorbed")),):
            if over is None:
                continue
            if not over.get("instruction"):
                bad.append(f"masthead.{key}.{name} has no instruction")
            if not over.get("fallback"):
                bad.append(f"masthead.{key}.{name} has no fallback: an offline "
                           "morning that absorbs a slot prints nothing there")
            cap = over.get("max_chars", 0)
            longest = max((len(x) for x in (over.get("fallback") or [])), default=0)
            if cap and longest > cap:
                bad.append(f"masthead.{key}.{name}: a fallback is {longest} "
                           f"chars, over max_chars {cap}")
        pool_all = list(field.get("fallback") or [])
        for lists in (field.get("fallbacks") or []):
            pool_all += list(lists)
        if field.get("classes") is not None:
            if not isinstance(field["classes"], list) or not field["classes"]:
                bad.append(f"masthead.{key}: classes must be a non-empty list")
            else:
                notes.append(f"masthead.{key}: one of {len(field['classes'])} "
                             "classes per appearance, all before a repeat "
                             "(main.for_the_day)")
        if "chance" in field:
            if not 0 < float(field["chance"]) < 1:
                bad.append(f"masthead.{key}: chance must be between 0 and 1")
            else:
                notes.append(f"masthead.{key}: prints on about "
                             f"{float(field['chance']):.0%} of mornings")
        # A field whose lines carry their own heading has to carry one in every
        # fallback too, or an offline morning prints a heading-shaped sentence
        # in the middle of the line instead of a chip beside it.
        labelled = [bool(main.LABELLED_LINE.match(x)) for x in pool_all]
        if persona.get("masthead_label_lines") and any(labelled) and not all(labelled):
            bad.append(f"masthead.{key}: {labelled.count(False)} of "
                       f"{len(labelled)} fallbacks have no HEADING: prefix")
        if not field.get("instruction"):
            bad.append(f"masthead.{key} has no instruction")
        pools = field.get("fallbacks")
        if pools is not None:
            if len(pools) != variants:
                bad.append(f"masthead.{key}: {len(pools)} fallback lists for {variants} variants")
            for i, pool in enumerate(pools):
                if not pool:
                    bad.append(f"masthead.{key}: fallback list {i} is empty")
                lengths.append(len(pool))
        else:
            pool = field.get("fallback") or []
            if not pool:
                bad.append(f"masthead.{key} has no fallback: an offline morning prints nothing there")
            lengths.append(len(pool))
        longest = max((len(x) for x in (field.get("fallback") or [])), default=0)
        cap = field.get("max_chars", 0)
        if cap and longest > cap:
            bad.append(f"masthead.{key}: a fallback is {longest} chars, over max_chars {cap}")
    # A picture's caption field gets its fallback at run time, as long as the
    # others, from what the photograph shows (main.with_picture).
    captioned = (persona.get("picture") or {}).get("field", "caption") \
        if persona.get("picture") else None
    if captioned and captioned not in (persona.get("masthead") or {}):
        bad.append(f"picture: masthead.{captioned}, which captions it, is not declared")
    lengths = [n for n, k in zip(lengths, persona.get("masthead") or {}) if k != captioned]
    if lengths and len(set(lengths)) > 1:
        notes.append(f"masthead fallback lists differ in length {sorted(set(lengths))}: "
                     "the pick uses the shortest, so the tail of the longer ones never prints")

    speakers = persona.get("speakers")
    if speakers and not all(isinstance(s, str) and s.isupper() for s in speakers):
        bad.append("speakers must be the names as written in the text, in upper case")
    if persona.get("wants_history") and "history" not in persona:
        notes.append("wants_history: figures are attached at run time (main.with_history)")

    if persona.get("audition"):
        notes.append("in audition: never drawn")
    return bad, notes


def check_block(key: str, spec: dict, notes: list[str]) -> list[str]:
    """Problems with one `[persona.blocks.<key>]` table; notes appended."""
    bad = []
    if not (spec.get("form") or "").strip():
        bad.append(f"blocks.{key} has no form")
    layout, labels = spec.get("layout"), spec.get("labels") or []
    if layout not in (None, "lines", "labelled"):
        bad.append(f"blocks.{key}: layout {layout!r} is not lines or labelled")
    if labels and layout != "labelled":
        bad.append(f"blocks.{key}: labels are only read by layout = \"labelled\"")
    picks = spec.get("picks")
    if picks is not None:
        if not isinstance(picks, list) or not picks:
            bad.append(f"blocks.{key}: picks must be a non-empty list")
            picks = []
        for i, pick in enumerate(picks):
            if not (pick.get("brief") or pick.get("label")):
                bad.append(f"blocks.{key}: pick {i} has neither brief nor label")
        if picks:
            notes.append(f"blocks.{key}: one of {len(picks)} picks per appearance, "
                         "all of them before a repeat (main.rotate)")
    if "chance" in spec:
        if not 0 < float(spec["chance"]) < 1:
            bad.append(f"blocks.{key}: chance must be between 0 and 1")
        if not (spec.get("lucky") and spec.get("unlucky")):
            bad.append(f"blocks.{key}: a chance needs both lucky and unlucky lines")
    prefix = spec.get("fine_prefix")
    if prefix is not None and not (isinstance(prefix, str) or (
            isinstance(prefix, list) and prefix and all(isinstance(p, str) for p in prefix))):
        bad.append(f"blocks.{key}: fine_prefix must be a string or a list of strings")
    # A drawing that is not registered prints nothing and says nothing, so
    # name it here; and its own offline copy has to be in the block's shape too.
    drawn = []
    if "drawing" in spec:
        bad += check_drawing(key, spec, notes)
        if not bad:
            import importlib
            module, fn = main.DRAWINGS[spec["drawing"]]
            make = getattr(importlib.import_module(module), fn)
            drawn = [make(spec, turn) for turn in (0, 1, 8)]
    # The offline copy has to come out in the block's own shape, or a morning
    # with no narrator prints a form with its fields run together.
    copies = ([p for p in (picks or []) if p.get("body")] + list(spec.get("fallback") or [])
              + [d for d in drawn if d and d.get("body")])
    for i, copy in enumerate(copies):
        if not (copy.get("body") or "").strip():
            bad.append(f"blocks.{key}: offline copy {i} has no body")
        elif layout == "labelled":
            rows = main.block_lines(copy["body"], spec) or []
            if any(not row["label"] for row in rows):
                bad.append(f"blocks.{key}: offline copy {i} has a line with no label")
    return bad


def check_drawing(key: str, spec: dict, notes: list[str]) -> list[str]:
    """Problems with a block's `drawing`: registered, and for the treasure
    map, maps that exist and draw clean (render/treasure_map.py)."""
    name = spec["drawing"]
    if name not in main.DRAWINGS:
        return [f"blocks.{key}: drawing {name!r} is not one of main.DRAWINGS "
                f"({', '.join(main.DRAWINGS)})"]
    if name != "treasure_map":
        return []
    from render.treasure_map import GRID, LANDMARKS, TreasureMap
    maps = spec.get("maps") or []
    if not maps:
        return [f"blocks.{key}: a treasure_map drawing needs maps"]
    bad = []
    for i, m in enumerate(maps):
        if not ({"seed", "name", "landmarks"} <= set(m)):
            bad.append(f"blocks.{key}: map {i} needs seed, name and landmarks")
            continue
        kinds = [lm.get("kind") for lm in m["landmarks"]]
        if any(k not in LANDMARKS for k in kinds):
            bad.append(f"blocks.{key}: map {m['name']!r}: landmark kinds are {', '.join(LANDMARKS)}")
            continue
        # The listed seeds are the reviewed ones: map_for would quietly swap a
        # faulty one for its neighbour, which is not the map that was looked at.
        faults = TreasureMap(m["seed"], m["name"], m["landmarks"]).faults()
        if faults:
            bad.append(f"blocks.{key}: map {m['name']!r} (seed {m['seed']}): {'; '.join(faults)}")
    if not bad:
        notes.append(f"blocks.{key}: {name}, {len(maps)} maps of {GRID * GRID} pieces, one piece "
                     f"per appearance ({len(maps) * GRID * GRID} mornings before new seeds)")
    return bad


def main_() -> int:
    show_coupons = "--coupons" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")]
    load_all()
    personas = main.load_personas(auditions=True)
    chosen = {k: v for k, v in personas.items() if not wanted or k in wanted}
    if wanted and not chosen:
        sys.exit(f"no such persona: {', '.join(wanted)}")

    problems = 0
    print(f"{'persona':22} {'coupon (vocabulary)':28} {'blocks':16} masthead")
    print("-" * 100)
    for name, persona in chosen.items():
        blocks = ", ".join(persona.get("blocks", {})) or "-"
        heads = ", ".join(persona.get("masthead", {})) or "-"
        vocab = persona.get("vocabulary", {}).get("coupon", "-")
        print(f"{name:22} {vocab:28} {blocks:16} {heads}")
        bad, notes = check(persona)
        for line in bad:
            problems += 1
            print(f"  ! {line}")
        for line in notes:
            print(f"  . {line}")
        if show_coupons:
            coupon = (persona.get("blocks") or {}).get("coupon")
            print("    coupon: " + (" ".join(main.block_spec(coupon)["form"].split())
                                    if coupon else
                                    "(none - the slot's own instruction stands)"))
    print("-" * 100)
    print(f"{len(chosen)} personas, {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main_())
