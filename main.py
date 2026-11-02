"""quick-guthe - the morning receipt.

    python main.py --preview            render today to PNG
    python main.py --date 2026-12-21    force a date (a simulation: never recorded)
    python main.py --offline            fixtures only, no network
    python main.py --no-narrator        live facts, templated copy, no API call
    python main.py --dry-run            full pipeline, no paper
    python main.py                      print
    python main.py --contact-sheet 30   30 simulated days side by side, offline

Pipeline:

    persona.pick -> slots.select -> collectors -> narrator -> render -> emit

Every stage degrades rather than raising: a dead source drops its slot, and a
failed or missing narrator leaves each slot's own templated copy in place.
`render_day` is that pipeline up to the render, for one day; `main` emits and
records what it returns, and the contact sheet lays thirty of them side by side.
"""

from __future__ import annotations

import argparse
import html
import importlib
import io
import random
import re
import sys
import textwrap
import tomllib
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageDraw, ImageFont, ImageOps

import cipher as ciphers
import config
import legendary
import narrator
import selection
from data.store import Store
from printer import get_printer
from printer.base import WIDTH_DOTS
from render import (BudgetExceeded, Renderer, atkinson, contrast_score, img_tag,
                    weather_layouts)
from render.barcode import code39
from render.fonts import (FONT_DIR, MONO_FAMILY, bold_weight, face_css, manifest,
                          mono_face_css, mono_stack, sizes, stack)
from slots import Context, safe_fetch
from slots.base import SlotFailure
from slots.registry import all_slots, get, load_all

ROOT = Path(__file__).resolve().parent
PERSONAS = ROOT / "personas"

# Spine slots feed the template's purpose-built blocks rather than the generic
# slot loop - a dedicated layout beats stacked generic sections, and the coupon
# in particular has to be last, below the tear line.
WEATHER_IDS = {2, 3, 4, 5}
NEWS_ID = 10
COUPON_ID = 11
LEGALESE_ID = 146
SPINE_IDS = WEATHER_IDS | {NEWS_ID, COUPON_ID, LEGALESE_ID}
PRICE = {"common": 0.30, "uncommon": 1.20, "rare": 6.00, "legendary": 50.00}

# Which slot each `[persona.vocabulary]` key belongs to. Without this the
# narrator receives a list of renames with no indication of what they are for,
# and puts one on the wrong section - a joke printed under TODAY'S MISSION,
# which is the micro-dare's name.
VOCAB_SLOTS = {"weather": 2, "news": NEWS_ID, "coupon": COUPON_ID,
               "micro_dare": 51, "banger": 93}

# Which slot each `[persona.blocks]` key belongs to. A block is a section whose
# SHAPE the persona may bend, not just its name: the legalese need not be terms
# and conditions, and the coupon need not be a coupon. The line written there is
# handed to that slot's narrator instruction as this persona's own version of
# it, so the Oracle's small print is a warning read aloud and the First Mate's
# is the ship's articles - the slot still supplies the joke and the subject.
BLOCK_SLOTS = {"weather": 2, "news": NEWS_ID, "coupon": COUPON_ID,
               "legalese": LEGALESE_ID}


def block_spec(value: str | dict) -> dict:
    """A `[persona.blocks]` entry as a table.

    A bare string is the form alone. The table adds what a form cannot do
    (personas.toml has the keys): a daily `picks` draw, a `layout` that sets the
    body as lines, a `chance` of a lucky morning, and the persona's own offline
    copy. Returns a copy.
    """
    return {"form": value} if isinstance(value, str) else dict(value)


def rotate(items: list, turn: int, salt: str):
    """Item `turn` of a shuffled round of `items`: all of them before a repeat.

    A persona prints once a fortnight, so a draw seeded by the date can land the
    same pick on consecutive appearances - which is exactly the sameness a pick
    exists to stop. `turn` therefore counts appearances, and each round of the
    list is shuffled with its own seed, so round two is not round one again.
    """
    round_, i = divmod(turn, len(items))
    order = list(range(len(items)))
    random.Random(f"{salt}:{round_}").shuffle(order)
    return items[order[i]]


# Drawings a block may carry ([persona.blocks.<key>] drawing): module and
# function, called with the block's table and the day's turn. Each returns a
# pick - brief, label, offline body and fine - plus the `svg` itself.
DRAWINGS = {"treasure_map": ("render.treasure_map", "piece_for")}


def today_block(name: str, key: str, spec: dict, day: Date, turn: int,
                number: int | None = None, store: Store | None = None) -> dict:
    """One block as it is today: its pick drawn, its luck decided, its
    drawing made.

    A lucky line may say `{no}` for the receipt number, which is what the
    theme prints on the ticket - the narrator cannot read the number off a
    ticket it has never seen.

    A drawing is the pick, when a block has one: the First Mate's coupon is
    piece `turn` of a treasure map, and what is on that piece is what the
    narrator is told and what the offline copy says.
    """
    out = dict(spec)
    if spec.get("picks"):
        out["pick"] = rotate(spec["picks"], turn, f"pick:{name}:{key}")
    if spec.get("drawing") in DRAWINGS:
        module, fn = DRAWINGS[spec["drawing"]]
        try:
            out["pick"] = getattr(importlib.import_module(module), fn)(
                spec, turn, day=day, number=number, store=store, name=name) or None
        except Exception:  # noqa: BLE001 - a broken drawing drops the drawing, not the page
            out.pop("pick", None)
    if "chance" in spec:
        out["is_lucky"] = random.Random(
            f"luck:{name}:{key}:{day.isoformat()}").random() < float(spec["chance"])
        for line in ("lucky", "unlucky"):
            if spec.get(line):
                out[line] = spec[line].replace(
                    "{no}", f"{number:04d}" if number else "the one printed on it")
    return out


def block_instruction(spec: dict) -> str:
    """The persona's form for a block, and today's draw, for the narrator."""
    text = f"This persona's own form for this section: {spec['form'].strip()}"
    pick = spec.get("pick")
    if pick:
        what = pick.get("brief") or pick.get("label", "")
        text += f"\n\nTODAY'S DRAW, WHICH IS NOT NEGOTIABLE: {' '.join(what.split())}"
    if "is_lucky" in spec:
        line = spec.get("lucky" if spec["is_lucky"] else "unlucky", "")
        if line:
            text += f"\n\nTODAY, AND THIS IS A FACT: {' '.join(line.split())}"
    if spec.get("layout"):
        text += ("\n\nPut each line on a line of its own, with a newline between "
                 "them, and nothing before the first.")
    return text


def block_fallbacks(persona: dict, spine: dict, written: set[int],
                    day: Date) -> None:
    """A persona's own offline copy for a block the narrator did not write.

    Without it a ration card prints the slot's generic coupon - "one good
    coffee" under RATION CARD - and a form laid out as lines prints one line.
    A pick may carry its own `body`, which wins, since it belongs to the thing
    drawn; otherwise the block's `fallback` list, by date. Mutates `spine`.
    """
    for key, sid in (("coupon", COUPON_ID), ("legalese", LEGALESE_ID)):
        part, raw = spine.get(sid), (persona.get("blocks") or {}).get(key)
        if part is None or raw is None or sid in written:
            continue
        spec = block_spec(raw)
        copy = spec.get("pick") if (spec.get("pick") or {}).get("body") else None
        if copy is None and spec.get("fallback"):
            copy = random.Random(f"fallback:{persona['name']}:{key}:"
                                 f"{day.isoformat()}").choice(spec["fallback"])
        if copy:
            part.body = copy["body"].strip()
            part.fine = (copy.get("fine") or "").strip() or None


# A labelled line in a block laid out as lines: "KNOWN ISSUE: unit has begun..."
# Same shape as a masthead's LABELLED_LINE below, a little longer, because a
# block's labels are the form's own ("ADDED (UNAUTHORISED)").
BLOCK_LABEL = re.compile(r"^([A-Z][A-Z0-9 /'()&.-]{0,26}):\s*(\S.*)$")


def block_lines(text: str, spec: dict) -> list[dict] | None:
    """A block's body as lines ([persona.blocks.<key>] layout), escaped.

    "lines" sets one line per line. "labelled" also splits each line's label
    from its text, so a theme can set the label as a column and select a line
    by it (data-k). With `labels` declared the split does not depend on the
    model's newlines: it cuts before each known label wherever it falls, which
    is what a form with six fields needs when they come back as one paragraph.
    None for a block with no layout, which keeps its body as written.
    """
    layout = spec.get("layout")
    if not layout or not text:
        return None
    labels = spec.get("labels") or []
    rows: list[tuple[str, str]] = []
    if layout == "labelled" and labels:
        alt = "|".join(re.escape(lb) for lb in sorted(labels, key=len, reverse=True))
        parts = re.split(rf"(?:^|\s+)({alt}):\s*", text.strip(), flags=re.I)
        if parts[0].strip():
            rows.append(("", parts[0].strip()))
        canon = {lb.upper(): lb for lb in labels}
        rows += [(canon.get(lb.upper(), lb.upper()), said.strip())
                 for lb, said in zip(parts[1::2], parts[2::2]) if said.strip()]
    else:
        for line in (ln.strip() for ln in text.splitlines()):
            if not line:
                continue
            marked = BLOCK_LABEL.match(line) if layout == "labelled" else None
            rows.append((marked[1], marked[2]) if marked else ("", line))
    return [{"k": re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"),
             "label": html.escape(label), "text": html.escape(said)}
            for label, said in rows]


def unprefixed(fine: str | None, spec: dict | None) -> str | None:
    """The small print without the words the theme already prints before it.

    A stylesheet that sets "shouts out to:" or "IF I DO NOT TRANSMIT:" in front
    of the footnote prints it twice when the narrator writes it as well, which
    it does, told or not. `fine_prefix` names those words so they can go - one
    string, or a list when the narrator has more than one way of saying it
    ("Scrawled on the back:").
    """
    prefix = (spec or {}).get("fine_prefix")
    if not fine or not prefix:
        return fine
    alt = "|".join(re.escape(p) for p in sorted([prefix] if isinstance(prefix, str) else prefix,
                                                key=len, reverse=True))
    return re.sub(rf"^\s*(?:{alt})(?!\w)\s*[:\-–—]?\s*", "", fine, flags=re.I) or None


def block_view(spec: dict | None, body: str) -> dict:
    """What the template needs beyond the text: the pick's label, the body as
    lines, and the pick's other fields as data attributes for the theme."""
    spec = spec or {}
    pick = spec.get("pick") or {}
    data = {re.sub(r"[^a-z0-9-]", "", k.lower()): v for k, v in pick.items()
            if k not in ("label", "brief", "body", "fine", "svg")
            and isinstance(v, (str, int, float))}
    if "is_lucky" in spec:
        data["lucky"] = int(spec["is_lucky"])
    # A drawing is markup Python made (DRAWINGS), never narrated text.
    return {"label": pick.get("label", ""), "lines": block_lines(body, spec),
            "data": data, "drawing": pick.get("svg", "")}


# Worn by a persona in audition until it has a stylesheet of its own.
AUDITION_THEME = "_audition.css"


def with_reader(value, marks: dict[str, str]):
    """`value` with every mark replaced, in every string at any depth."""
    if isinstance(value, str):
        for mark, text in marks.items():
            value = value.replace(mark, text)
        return value
    if isinstance(value, list):
        return [with_reader(v, marks) for v in value]
    if isinstance(value, dict):
        return {k: with_reader(v, marks) for k, v in value.items()}
    return value


def load_personas(auditions: bool = False) -> dict[str, dict]:
    """The pool. Personas still in audition are left out unless asked for.

    An auditioning persona is not designed yet, so it is never drawn - and it is
    kept off the rival lists too: a persona that has never printed is not one the
    others can have a grudge against. `--persona` asks for them, which is how a
    voice gets heard before its design exists.

    personas.toml writes `{name}` where the reader's name goes, `{NAME}` for it
    in capitals and `{initial}` for its first letter (`config.reader_name`).
    """
    data = tomllib.loads((PERSONAS / "personas.toml").read_text(encoding="utf-8"))
    name = config.reader_name()
    marks = {"{name}": name, "{NAME}": name.upper(),
             "{initial}": name[:1].upper()}
    return {p["name"]: with_reader(p, marks) for p in data["persona"]
            if auditions or not p.get("audition")}


def css_string(text: str) -> str:
    """`text` as a quoted CSS string, for `content` and custom properties."""
    text = " ".join(text.split()).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


PERSONA_TIERS = ("common", "uncommon", "rare")


def pick_persona(personas: dict, day: Date, forced: str | None,
                 store: Store | None = None) -> dict:
    """The day's persona: seeded, weighted by rarity, damped by recency.

    Rarity here is not how good a persona is, it is how fast it wears out. A
    persona with somewhere to go on an ordinary Tuesday is common; one that is
    the same strong joke every time it lands is not. The tier weights in
    `[personas]` are shared by every member of a tier, so adding a persona makes
    its tier-mates rarer rather than making the tier more likely - the odds of
    *a* rare morning stay put however many rares get written.

    Recency then damps whatever printed lately, on the same curve as the slots
    but slower to recover: a repeat reads as a fault to a reader who only sees
    one page a day, and two Clerks in a week would look like the draw is broken
    even when it is honest. A persona that has never printed is undamped, so a
    debut lands early rather than waiting its turn.

    The seed is the date alone, but the result is not a pure function of it:
    it depends on what the machine remembers printing. Re-running
    a past day after the fact can therefore hand back a different persona, which
    is correct - the history it was drawn against has moved on.
    """
    if forced:
        if forced not in personas:
            sys.exit(f"--persona {forced}: no such persona. "
                     f"Have: {', '.join(personas)}")
        return personas[forced]
    live = [p for p in personas.values()
            if not p.get("retired") and not p.get("audition")]
    weights = {t: float(config.get("personas", t, default=w)) for t, w in
               (("common", .50), ("uncommon", .35), ("rare", .15))}
    suppression = float(config.get("personas", "suppression", default=0.95))
    tau = float(config.get("personas", "tau_days", default=14))
    seen = store.personas_last_seen(day) if store else {}

    # Tier first, then who within it - the shape the slot engine uses, and not
    # merely a tidier spelling of one weighted list over all sixteen. Scoring
    # them in one pass lets recency leak across tiers: commons print oftenest,
    # so at any moment more commons are freshly damped, and the mass that
    # damping frees goes to whoever is not - which quietly pushed rare mornings
    # from 15% to nearly 18% in simulation. Drawing the tier first spends it
    # inside the tier instead, where it belongs.
    pool: dict[str, list[dict]] = {}
    for persona in live:
        pool.setdefault(persona.get("rarity", "common"), []).append(persona)

    rng = random.Random(f"persona:{day.isoformat()}")
    tiers = [t for t in PERSONA_TIERS if pool.get(t)]
    tier = rng.choices(tiers, weights=[weights.get(t, 0.0) for t in tiers])[0]

    candidates = pool[tier]
    scored = []
    for persona in candidates:
        last = seen.get(persona["name"])
        days = (day - last).days if last else None
        scored.append(selection.recency_multiplier(days, suppression, tau))
    if not any(scored):                        # all of them printed just now
        scored = [1.0] * len(candidates)
    return rng.choices(candidates, weights=scored)[0]


def absorb(persona: dict, rotating: list[dict]) -> dict:
    """Fold any drawn slot this persona's masthead swallows into that masthead.

    Some personas say the same thing twice. OPS files the day's orders at the
    top of the page - SITUATION, MISSION, EXECUTION - and the micro-dare (51)
    is a one-line instruction for the day as well, which OPS then prints lower
    down under the heading TODAY'S MISSION. Two missions on one sheet is one
    too many, and the duplication is not the slot's fault or the masthead's: it
    is what happens when a persona's own furniture grows into a slot's job.

    `[persona.absorbs]` maps a slot id to the masthead field that eats it. On a
    day the slot is drawn, its section is not printed; instead that field is
    written from the slot's own text, at length, and the theme sets it at scale
    (`data-absorbed` on the masthead names the field). Each masthead field may
    carry an `absorbed` table - its own instruction, max_chars and fallbacks for
    the days it is carrying a slot as well as itself.

    The line stays in the itemization and in the recorded draw. It was drawn and
    it is on the paper; it has only moved up the page, and a receipt that did
    not list it would be lying about what it printed.
    """
    plan = {int(k): v for k, v in (persona.get("absorbs") or {}).items()}
    if not plan:
        return persona
    eaten: dict[str, dict] = {}
    for item in rotating:
        key = plan.get(item["id"])
        if key:
            item["absorbed"] = True
            eaten[key] = item
    if not eaten:
        return persona

    fields = {}
    for key, field in (persona.get("masthead") or {}).items():
        item = eaten.get(key)
        if item is None:
            fields[key] = field
            continue
        field = {**field, **(field.get("absorbed") or {})}
        text = " ".join(str(item.get("body") or "").split())
        if text:
            # The narrator is handed the drawn task itself, because the field is
            # now that task. Without this the mission would be invented beside a
            # dare nobody can see, and the itemization would price a section the
            # page does not contain.
            field["instruction"] = (
                field["instruction"].rstrip() + "\n\nTODAY THIS FIELD IS ALSO "
                f'THE DAY\'S TASK, WHICH HAS ALREADY BEEN SET: "{text}"\n'
                "Write that task as this field, in this persona's voice - the "
                "same instruction, issued rather than suggested. Do not invent a "
                "different task and do not soften this one.")
        fields[key] = field
    return {**persona, "masthead": fields, "absorbed": sorted(eaten)}


def theme_css(persona: dict) -> str:
    """The persona's stylesheet, or the audition placeholder while it has none.

    Only a persona in audition may fall back, and only while its own file does
    not exist - so a theme being written during an audition previews as itself
    from its first line. A live persona with no stylesheet is a real fault and
    is not quietly dressed in a stand-in.

    A persona may also wear a second stylesheet over the first (`theme_overlay`),
    which is appended after it and therefore wins. Only the Mimic asks: it wears
    somebody else's theme, and its own mistakes have to be layered on top of
    whichever one that turns out to be.
    """
    path = PERSONAS / "themes" / persona["theme"]
    if persona.get("audition") and not path.exists():
        path = PERSONAS / "themes" / AUDITION_THEME
    css = path.read_text(encoding="utf-8")
    overlay = persona.get("theme_overlay")
    if overlay:
        css += "\n" + (PERSONAS / "themes" / overlay).read_text(encoding="utf-8")
    return css


def gather(ctx: Context) -> tuple[dict, list[dict], list[SlotFailure],
                                  "selection.Draw"]:
    """Draw today's slots, then fetch only those.

    Selection happens *before* fetching, deliberately: a slot that was not drawn
    should cost nothing, and several of them reach the network. Fetching first
    and discarding would spend requests on content nobody reads.
    """
    load_all()
    failures: list[SlotFailure] = []
    spine: dict = {}
    rotating: list[dict] = []

    registry = all_slots()
    draw = selection.select(ctx.date, registry, store=ctx.store,
                            offline=ctx.offline)
    drawn_ids = {s.spec.id for s in draw.slots}
    # Visible to the slots before any of them run. The changelog needs to know
    # what is appearing today to announce a debut, and tomorrow-predicted needs
    # it to grade yesterday's guess against what was actually drawn.
    ctx.shared["drawn_ids"] = sorted(drawn_ids)

    for slot in registry:
        is_spine = slot.spec.id in SPINE_IDS
        if not is_spine and slot.spec.id not in drawn_ids:
            continue
        result = safe_fetch(slot, ctx, failures)
        if result is None:
            continue
        if is_spine:
            spine[slot.spec.id] = result
            continue
        rotating.append({
            "id": slot.spec.id,
            "tier": slot.spec.tier,
            "name": slot.spec.name,
            "head": result.head,
            "body": result.body,
            "image": img_tag(result.image) if result.image is not None else None,
            "fine": result.fine,
            "fallback": result.fallback,
            "answer": result.answer,
            "brief": result.brief,
            "needs_narrator": slot.spec.needs_narrator,
            "needs_search": slot.spec.needs_search,
        })
    return spine, rotating, failures, draw


def narrate(day: Date, persona: dict, spine: dict, rotating: list[dict],
            store: Store, record: bool = False) -> "narrator.Narration | None":
    """Hand the day's facts to the narrator and apply what comes back.

    Mutates `spine` results and `rotating` entries in place. Anything the
    narrator did not write keeps the slot's own templated copy, so a partial
    response degrades section by section rather than all at once.
    """
    load_all()
    specs = {s.spec.id: s.spec for s in all_slots()}

    # A persona's settled rename for a section, handed to that section alone.
    suggested = {slot_id: persona.get("vocabulary", {})[key]
                 for key, slot_id in VOCAB_SLOTS.items()
                 if key in persona.get("vocabulary", {})}

    # A persona's own shape for a block section ([persona.blocks]).
    blocks = {slot_id: block_spec(persona["blocks"][key])
              for key, slot_id in BLOCK_SLOTS.items()
              if key in persona.get("blocks", {})}

    def brief_for(sid: int, brief: dict) -> dict:
        brief = dict(brief)
        if sid in suggested:
            brief["this_persona_calls_this_section"] = suggested[sid]
        if sid in blocks:
            brief["instruction"] = (
                f"{brief.get('instruction', '').rstrip()}\n\n"
                f"{block_instruction(blocks[sid])}\n"
                "Keep everything above - the subject, the facts and the joke - "
                "and write it as that.")
        return brief

    narrated: list[dict] = []
    for sid, result in spine.items():
        if specs[sid].needs_narrator:
            brief = brief_for(sid, result.brief)
            narrated.append({"id": sid, "name": specs[sid].name,
                             "brief": brief, "current": result.body,
                             "needs_search": specs[sid].needs_search})
    for item in rotating:
        # An absorbed slot has no section of its own today (`absorb`): its text
        # went into a masthead field, which is narrated as part of the masthead.
        # Asking for a body as well would spend tokens on prose nobody prints.
        if item["needs_narrator"] and not item.get("absorbed"):
            brief = brief_for(item["id"], item["brief"])
            narrated.append({"id": item["id"], "name": item["name"],
                             "brief": brief, "current": item["body"],
                             "needs_search": item.get("needs_search", False)})

    # The digest names each morning's persona by what the others call it, not by
    # its file key: the Clerk remarks on yesterday's keeper and the Roll corrects
    # its coverage of the others, and "MONKEY-ASTRONAUT" is a key, not a name.
    names = {name: p.get("display", name)
             for name, p in load_personas(auditions=True).items()}
    receipts = [dict(r, persona=names.get(r["persona"], r["persona"]))
                for r in store.recent_receipts(14)]
    result = narrator.write(day, persona, narrated, receipts=receipts)
    if result is None:
        return None

    for sid, header in result.headers.items():
        if sid in spine:
            spine[sid].head = header
        for item in rotating:
            if item["id"] == sid:
                item["head"] = header
    for sid, body in result.bodies.items():
        # A fallback body's small print describes the fallback (`SlotResult`),
        # so it leaves with it - before the narrator's own fines are applied.
        if sid in spine:
            spine[sid].body = body
            if spine[sid].fallback:
                spine[sid].fine = None
        for item in rotating:
            if item["id"] == sid:
                item["body"] = body
                if item.get("fallback"):
                    item["fine"] = None
    for sid, fine in result.fines.items():
        if sid in spine:
            spine[sid].fine = fine or None
        for item in rotating:
            if item["id"] == sid:
                item["fine"] = fine or None

    # Hand each slot what the narrator actually wrote, so the few that need to
    # keep it can: search slots caching a finding as tomorrow's fallback, the
    # running bit keeping the joke it invented. Real mornings only - a preview
    # must never become part of the machine's memory.
    if record:
        for item in rotating:
            if item["id"] not in result.bodies:
                continue
            try:
                get(item["id"]).after_narration(store, day, item["head"],
                                                item["body"])
            except Exception:  # noqa: BLE001 - memory is never worth a crash
                pass
    return result


def _vocab(persona: dict, key: str, fallback: str) -> str:
    return persona.get("vocabulary", {}).get(key, fallback)


def news_block(parts: dict, persona: dict) -> dict | None:
    news = parts.get(NEWS_ID)
    if news is None or not news.body:
        return None
    return {"head": _vocab(persona, "news", news.head),
            "headlines": news.body.splitlines()}


def coupon_block(parts: dict, persona: dict) -> dict | None:
    coupon = parts.get(COUPON_ID)
    if coupon is None:
        return None
    raw = (persona.get("blocks") or {}).get("coupon")
    spec = block_spec(raw) if raw else None
    return {"head": _vocab(persona, "coupon", coupon.head),
            "body": coupon.body, "terms": unprefixed(coupon.fine, spec),
            **block_view(spec, coupon.body)}


def legalese_block(parts: dict, persona: dict | None = None) -> dict | None:
    legal = parts.get(LEGALESE_ID)
    if legal is None:
        return None
    raw = ((persona or {}).get("blocks") or {}).get("legalese")
    spec = block_spec(raw) if raw else None
    return {"body": legal.body, "footnote": unprefixed(legal.fine, spec),
            **block_view(spec, legal.body)}


def weather_block(parts: dict, persona: dict) -> dict | None:
    """Map slots 2/3/4/5 onto the template's weather section.

    Any of them may be missing - a dropped slot must leave a hole, not an
    exception. The block itself disappears only if all four are gone.
    """
    if not parts:
        return None
    verdict, chart, delta, sun = (parts.get(i) for i in (2, 3, 4, 5))
    facts = verdict.brief if verdict else {}

    # "Feels like" earns a line only when it disagrees with the real figure.
    # Printing "feels like 19" beside "19" is noise, and the whole point of the
    # element is that the two numbers worth having are easy to find.
    feels = ""
    if "feels_low_c" in facts and abs(facts["feels_low_c"] - facts["low_c"]) >= 2:
        feels = f"feels like {facts['feels_low_c']:.0f}°"

    # Whole degrees, except on a flat day. A day running 17.6 to 18.4 is real
    # and prints as "18 / 18", which reads as a fault rather than as a flat day.
    # One decimal only when the rounded figures collide keeps the common case
    # clean and the odd case honest.
    low = high = ""
    if "low_c" in facts:
        places = 0 if round(facts["low_c"]) != round(facts["high_c"]) else 1
        low = f"{facts['low_c']:.{places}f}°"
        high = f"{facts['high_c']:.{places}f}°"

    # The persona's own way of drawing the day (SYSTEM.md 3, render/
    # weather_layouts.py). The facts are the same five whichever it picks; an
    # unknown name, or a forecast too thin to draw, falls back to the plain
    # arrangement in the template.
    forecast = (chart.extra or {}).get("forecast") if chart else None
    layout = weather_layouts.block(persona.get("weather", weather_layouts.DEFAULT), {
        "today": forecast.today if forecast else None,
        "yesterday": forecast.yesterday if forecast else None,
        "tomorrow": forecast.tomorrow if forecast else None,
        "verdict": verdict.body if verdict else "",
        "low": low, "high": high, "feels": feels,
        "delta": delta.body if delta else "",
        "sun": sun.body if sun else "",
        "daylight": sun.fine if sun else "",
    })

    return {
        "head": _vocab(persona, "weather", "Weather"),
        "layout": layout,
        "verdict": verdict.body if verdict else "",
        "chart_svg": chart.body if chart else "",
        "delta": delta.body if delta else "",
        "low": low,
        "high": high,
        "feels": feels,
        "sun": sun.body if sun else "",
        "daylight": sun.fine if sun else "",
        "stale": verdict.fine if verdict else None,
        # A fact a theme may draw on: rain is forecast today (the Commentary
        # Box pulls the covers on). Never a decision about what prints.
        "wet": bool(facts.get("rain_windows")),
    }


def variant_of(persona: dict, day: Date) -> int:
    """Which of a theme's masthead variants prints today ([persona] variants).

    Rotated by date rather than drawn, so consecutive mornings never repeat a
    shot and a reprint gets the same one.
    """
    return day.toordinal() % max(1, int(persona.get("variants", 1)))


# A thermal roll is 80mm x 80m. The gauge on the Machine's footer is drawn from
# the paper recorded so far against that, which is an estimate and says so: the
# receipts table cannot know when a roll was changed.
ROLL_MM = 80_000


def with_history(persona: dict, store: Store) -> dict:
    """The persona, told what it has printed so far ([persona] wants_history).

    Only the Machine asks. It is trying to work out what it is from the only
    instruments it has, and "I HAVE PRINTED 41 TIMES" is one of them - so the
    figures are real, or it says nothing. Returns a copy.
    """
    if not persona.get("wants_history"):
        return persona
    h = store.persona_history(persona["name"])
    facts = (f"Figures about yourself, true as recorded: you have printed "
             f"{h['appearances']} times"
             + (f", first on {h['first']}" if h["first"] else "")
             + f"; you have spent {h['paper_mm'] / 1000:.2f} metres of paper on "
             f"those, and {h['paper_mm_all'] / 1000:.2f} metres in total since "
             f"the machine was first switched on. Quote these exactly or not at "
             f"all; never invent another.")
    voice = persona.get("voice", "").rstrip()
    return dict(persona, voice=f"{voice}\n\n{facts}\n", history=h)


def with_stock(persona: dict, store: Store | None, day: Date) -> dict:
    """A share price for a persona that runs one ([persona.stock]).

    Accounts Receivable reports on a company whose only asset is the reader,
    and its share price is the one figure on that page that can be real: each
    receipt already has a price (its subtotal, the drawn slots at their
    rarity), so the closing price is today's and the history is every morning
    before it - read here from the receipts table, strictly before today so a
    reprint is the same. Today's close is added in `build_html`, once the day's
    slots are settled. Returns a copy.
    """
    spec = persona.get("stock")
    if not spec or store is None:
        return persona
    days = max(2, int(spec.get("days", 30)))
    rows = [r for r in store.recent_receipts(days + 7) if r["day"] < day.isoformat()]
    past = [round(sum(PRICE.get(tier, 0) * n for tier, n in (r.get("rarity") or {}).items()), 2)
            for r in rows[:days - 1]][::-1]
    return dict(persona, stock_today={"ticker": spec.get("ticker", "STOCK"),
                                      "past": past})


def stock_panel(spec: dict, close: float) -> dict:
    """Close, move and a sparkline for the template, from `with_stock`."""
    series = list(spec["past"]) + [close]
    prev = spec["past"][-1] if spec["past"] else None
    if prev is None:
        move = "NEW LISTING"
    elif abs(close - prev) < 0.005:
        move = "UNCH"
    else:
        arrow = "▲" if close > prev else "▼"
        pct = f" ({abs(close - prev) / prev * 100:.1f}%)" if prev else ""
        move = f"{arrow} {abs(close - prev):.2f}{pct}"
    w, h, pad = 200, 40, 4
    lo, hi = min(series), max(series)
    span = (hi - lo) or 1.0
    step = (w - 2 * pad) / max(1, len(series) - 1)
    pts = [(pad + i * step if len(series) > 1 else w / 2,
            h - pad - (v - lo) / span * (h - 2 * pad) if hi > lo else h / 2)
           for i, v in enumerate(series)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    x, y = pts[-1]
    svg = (f'<svg class="stock-line" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<polyline points="{line}" fill="none" stroke="#000" stroke-width="2.5" '
           f'stroke-linejoin="round" stroke-linecap="round"/>'
           f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#000"/></svg>')
    return {"ticker": spec["ticker"], "close": f"{close:.2f}", "move": move,
            "svg": svg, "span": f"LAST {len(series)} MORNINGS"
            if len(series) > 1 else "FIRST MORNING"}


def with_picture(persona: dict, day: Date, store: Store | None,
                 offline: bool = False) -> dict:
    """A real photograph for a masthead that runs one ([persona.picture]).

    The Daily Roll runs Wikimedia Commons' picture of the day, dithered to 1-bit
    here, at its final size, before it reaches the page (CLAUDE.md invariant 2).
    The photograph is a fact and its caption is the Roll's: the caption field is
    handed what the picture really shows, so the spin goes around the truth
    rather than through it, and falls back to a plain true caption with no
    narrator.

    No picture - offline with nothing cached, or one too flat to dither - and
    the caption field goes too, since a caption under nothing reads as a fault.
    The photo credit prints small under it, which is the licence's condition and
    a newspaper's habit. Returns a copy.
    """
    spec = persona.get("picture")
    if not spec:
        return persona
    field = spec.get("field", "caption")
    masthead = dict(persona.get("masthead") or {})
    picture = None
    try:
        from sources import wikipedia
        found = wikipedia.picture_of_the_day(day, store=store, offline=offline)
        picture = photograph(found["jpeg"], int(spec.get("width", 546)),
                             int(spec.get("max_height", 300)))
    except Exception:  # noqa: BLE001 - a dead source drops the picture, not the page
        found = None
    if picture is None:
        masthead.pop(field, None)
        return dict(persona, masthead=masthead)

    title = found["title"] or "a photograph"
    if field in masthead:
        about = " ".join(f"{title}. {found['description']}".split())[:420]
        caption = dict(masthead[field])
        caption["instruction"] = (
            caption.get("instruction", "").rstrip()
            + "\n\nTODAY'S PHOTOGRAPH, AS ITS SOURCE DESCRIBES IT - true, and "
            f"the only facts you have about it: {about}")
        # Index-aligned with the other fields' fallbacks (masthead_copy), so it
        # is as long as they are; every entry is the same plain, true caption.
        n = max((len(f.get("fallback") or []) for k, f in masthead.items()
                 if k != field), default=1)
        caption["fallback"] = [f"PICTURED: {title.upper()}"] * max(1, n)
        masthead[field] = caption
    artist = found.get("artist") or "Unknown"
    if len(artist) > 40:
        artist = artist[:40].rsplit(" ", 1)[0] + "..."
    credit = f"Picture: {artist} / Wikimedia" + (
        f", {found['licence']}" if found.get("licence") else "")
    return dict(persona, masthead=masthead,
                picture_today={"img": img_tag(picture, alt=html.escape(title)),
                               "credit": credit})


def photograph(jpeg: bytes, width: int, max_height: int):
    """A photograph for the page: sized, levelled, dithered - or None if flat.

    A landscape fills the width and is cut to `max_height` through its middle,
    where the subject usually is. A portrait is fitted to a third more height
    instead and inset, the way a paper runs an upright picture rather than
    cropping a face to its nose. Levelled before dithering, because a
    photograph that is all midtones dithers to an even grey
    (`render.dither.contrast_score`).
    """
    source = Image.open(io.BytesIO(jpeg)).convert("L")
    if source.height > source.width:
        max_height = round(max_height * 4 / 3)
        width = max(1, round(max_height * source.width / source.height))
    img = source.resize((width, max(1, round(source.height * width / source.width))),
                        Image.LANCZOS)
    if img.height > max_height:
        top = (img.height - max_height) // 2
        img = img.crop((0, top, img.width, top + max_height))
    img = ImageOps.autocontrast(img, cutoff=1)
    if contrast_score(img) < 0.16:
        return None
    return atkinson(img)


# The Mimic wears somebody else's theme and lays its own mistakes over the top.
MIMIC = "mimic"
MIMIC_OVERLAY = "mimic.css"

# How a name comes out when something that has only read the word tries to write
# it. One of these is applied, seeded by the date, so THE CLERK is THE CLERCK on
# one morning and THE CLERKK on another - and never two different spellings on
# one page, which would read as a typo rather than as a creature.
_SLIPS = (
    lambda w, i: w[:i + 1] + w[i] + w[i + 1:],            # a letter, twice
    lambda w, i: w[:i] + w[i + 1] + w[i] + w[i + 2:],     # two, the wrong way round
    lambda w, i: w[:i] + w[i + 1:],                       # one short
    # A lookalike, or - where the letter has none - the letter twice, because a
    # slip that changes nothing is not a slip and the name would print correctly.
    lambda w, i: w[:i] + {"C": "K", "K": "C", "S": "Z", "Z": "S", "I": "Y",
                          "Y": "I", "F": "PH", "O": "0", "E": "EE",
                          "A": "AA", "T": "TT"}.get(w[i].upper(),
                                                    w[i] * 2) + w[i + 1:],
)


def misspell(name: str, day: Date) -> str:
    """A display name as the Mimic writes it: right shape, one letter out.

    Applied to the longest word, because the joke has to be legible - a slip in
    "THE" is a typo, a slip in "CLERK" is a creature that has never seen the
    word written down.
    """
    words = name.split()
    if not words:
        return name
    n = max(range(len(words)), key=lambda i: len(words[i]))
    word = words[n]
    if len(word) < 4:
        return name
    rng = random.Random(f"misspell:{name}:{day.isoformat()}")
    slip = rng.choice(_SLIPS)
    i = rng.randrange(1, len(word) - 1)
    words[n] = slip(word, i)
    return " ".join(words)


def wears_today(personas: dict, day: Date, store: Store | None,
                forced: str | None = None) -> dict | None:
    """Whom the Mimic is impersonating: the most recent persona that is not it.

    It has studied the recent receipts, so the choice is the digest's - whoever
    printed last - and not a draw. Failing a memory (a fresh machine, or a run
    against a cache that has never seen anyone), a seeded pick, so the same
    morning always produces the same impostor. `None` when there is nobody at
    all to copy, which the voice handles: it impersonates "a human" in general,
    which goes worse.
    """
    pool = {name: p for name, p in personas.items()
            if name != MIMIC and not p.get("retired")}
    if forced:
        if forced not in pool:
            sys.exit(f"--wears {forced}: no such persona to impersonate. "
                     f"Have: {', '.join(pool)}")
        return pool[forced]
    if not pool:
        return None
    seen = store.personas_last_seen(day) if store else {}
    recent = [(d, n) for n, d in seen.items() if n in pool]
    if recent:
        return pool[max(recent)[1]]
    return pool[random.Random(f"wears:{day.isoformat()}").choice(sorted(pool))]


def mimicry(persona: dict, personas: dict, day: Date, store: Store | None,
            forced: str | None = None) -> dict:
    """The Mimic, dressed as somebody. Any other persona passes through.

    The disguise is a real one, and it is the whole page: it borrows the body
    and display faces, the accent face, the stylesheet, the variant count (so the
    borrowed theme's day-by-day shots still line up), the speakers, the section
    names and the masthead fields of whoever it is wearing. Nothing is held back
    to be recognisably the Mimic's, because the mistakes are the persona - a page
    that is somebody else's with things wrong in it is the joke, and a page
    carrying a second persona's furniture is just two personas.

    The voice is stacked rather than replaced: the impersonated persona's voice
    first, so the narrator has a character to do, then the Mimic's over the top,
    so what actually gets written is that character done badly by something with
    a second mouth. Returns a copy; the loaded personas are untouched.
    """
    if persona["name"] != MIMIC:
        return persona
    victim = wears_today(personas, day, store, forced)
    if victim is None:
        # Nobody to copy. It impersonates "a human" in general, in its own
        # stylesheet and its own faces - and still cannot spell the name it has
        # picked out for itself, which is the one part of the act that never
        # improves.
        return dict(persona, display=misspell(persona["display"], day))

    rng = random.Random(f"mimicry:{day.isoformat()}")
    worn = victim.get("display", victim["name"])

    # Its own words for the sections, over the top of the borrowed ones - two
    # of them, not all five. A page that renames everything is a different
    # persona; a page that renames two things is a persona with something wrong
    # with it.
    vocabulary = dict(victim.get("vocabulary", {}))
    mine = persona.get("vocabulary", {})
    for key in rng.sample(sorted(mine), min(2, len(mine))):
        vocabulary[key] = mine[key]

    # The blocks it is trying to copy, quoted into its own instruction so the
    # narrator can see what the right answer would have been. Everything else
    # about the block is the worn persona's - its draw, its layout, its offline
    # copy - because the borrowed stylesheet expects them: a ration card with no
    # ration drawn on it is not a disguise slipping, it is a broken page.
    blocks = {k: block_spec(v) for k, v in (victim.get("blocks") or {}).items()}
    for key, raw in (persona.get("blocks") or {}).items():
        mine = block_spec(raw)
        theirs = blocks.get(key)
        blocks[key] = {**(theirs or {}), "form": mine["form"].rstrip() + (
            f"\n\nWhat {worn} would really have written here, which you have "
            f"read and are working from: {' '.join(theirs['form'].split())}"
            if theirs else
            f"\n\nYou have never seen {worn} write one of these. You are "
            f"guessing from the shape of the page.")}
    # Marked as worn, so a drawing that keeps count (the First Mate's map
    # pieces, numbered by her own appearances) can forge its picture instead
    # of handing out a real piece out of turn.
    blocks = {k: dict(v, worn=True) for k, v in blocks.items()}

    # The borrowed masthead, written by the wrong thing. Its own line goes on
    # the end - the one place on the page it forgets to keep the disguise up.
    masthead = {}
    for key, field in (victim.get("masthead") or {}).items():
        field = dict(field)
        field["instruction"] = (field.get("instruction", "").rstrip()
                                + f"\n\nYou are not {worn}. You are wearing "
                                "them. Write this the way they would and get "
                                "exactly one thing in it wrong - a word used "
                                "slightly off, a detail no human would think "
                                "to mention, a fact about the ship. Never more "
                                "than one: it is a disguise, not a costume "
                                "party.")
        masthead[key] = field
    masthead.update(persona.get("masthead") or {})

    # The whole disguise, in one instruction. Everything above the rule is the
    # worn persona's own voice brief; everything below is the creature holding
    # it up in front of itself. The order matters - an impression has to be of
    # something specific, so the thing being impersonated goes first and in full,
    # and the line between them says plainly which one is speaking.
    voice = (victim.get("voice", "").rstrip() + "\n\n"
             + "-" * 62 + "\n"
             + f"EVERYTHING ABOVE IS THE VOICE OF {worn.upper()}. IT IS NOT "
             f"YOURS.\n\n"
             f"You are an alien doing an impression of {worn}, and it is not a "
             f"good impression. Not a parody, and not a different persona: a "
             f"sincere, effortful, close attempt at being {worn} that keeps "
             f"coming out wrong. Every section should be recognisably "
             f"{worn} - their subjects, their rhythm, their words, their whole "
             f"idea of what a morning is - performed by something that has read "
             f"them rather than been them, and that gets one thing wrong every "
             f"time it opens its mouth.\n\n"
             + persona.get("voice", "").rstrip())

    return dict(persona,
                wears=victim["name"],
                display=misspell(worn, day),
                font=victim["font"],
                # Every face borrowed, the accent included, except "own" - the
                # one it keeps, for the one line a page where it stops wearing
                # anybody. Keeping more of its own reads as a second persona
                # shouting over the first rather than a disguise slipping.
                fonts=dict(victim.get("fonts", {}),
                           **{k: v for k, v in persona.get("fonts", {}).items()
                              if k == "own"}),
                theme=victim["theme"],
                theme_overlay=MIMIC_OVERLAY,
                variants=victim.get("variants", 1),
                variant_briefs=victim.get("variant_briefs"),
                speakers=victim.get("speakers"),
                wants_history=victim.get("wants_history", False),
                # The Daily Roll's photograph comes with its caption field, and
                # a caption under no picture is not a mistake anyone would make.
                picture=victim.get("picture"),
                art_tags=list(victim.get("art_tags", []))
                + list(persona.get("art_tags", [])),
                vocabulary=vocabulary, blocks=blocks, masthead=masthead,
                voice=voice)


def for_the_day(persona: dict, day: Date, store: Store | None = None) -> dict:
    """The persona as it is today: its variant brief ([persona] variant_briefs)
    appended to its voice, a subject drawn for any masthead field that asks for
    one, and each block's pick and luck ([persona.blocks.<key>]).

    A variant that changes more than the drawing - the Commentary Box calling a
    different sport each day - has to reach the narrator too, or the page says
    rugby while the commentators talk cricket.

    `[persona.masthead.<key>] classes` is the second half of the same idea, one
    field down. A field with a wide brief and no steer writes the same good
    answer every morning: OPS's mission came back as a version of "clear the
    oldest item" however it was asked. Python picks the CLASS of thing - a
    deferred chore, a reconnection, a creative attempt - going round the list
    once per appearance, and the narrator writes what it actually is. Facts and
    choices in Python, voice in the model, which is the house split everywhere
    else.

    Returns a copy; the loaded persona is untouched.
    """
    out = dict(persona)
    briefs = persona.get("variant_briefs")
    if briefs:
        brief = briefs[variant_of(persona, day) % len(briefs)]
        voice = persona.get("voice", "").rstrip()
        out["voice"] = f"{voice}\n\nToday: {brief.strip()}\n"

    # Picks and classes go round once per appearance (`rotate`), counted from
    # the receipts strictly before today, so a reprint draws what today drew.
    turn = (store.appearances_before(persona["name"], day)
            if store is not None else day.toordinal())

    # A field may also print only some mornings (`chance`): the Monkey hears
    # from Ground about one morning in three, and on the others there is
    # nobody on the line. A field that does not print today is not asked for.
    spec = persona.get("masthead") or {}
    if any(f.get("classes") or "chance" in f for f in spec.values()):
        fields = {}
        for key, field in spec.items():
            if "chance" in field and random.Random(
                    f"mhluck:{persona['name']}:{key}:{day.isoformat()}"
            ).random() >= float(field["chance"]):
                continue
            pool = field.get("classes")
            if not pool:
                fields[key] = field
                continue
            pick = rotate(pool, turn, f"class:{persona['name']}:{key}")
            fields[key] = {**field, "instruction":
                           field["instruction"].rstrip()
                           + "\n\nTHIS MORNING'S CLASS, WHICH IS NOT NEGOTIABLE: "
                           + " ".join(pick.split())}
        out["masthead"] = fields

    blocks = persona.get("blocks") or {}
    if blocks:
        number = store.receipt_number_for(day) if store is not None else None
        out["blocks"] = {key: today_block(persona["name"], key, block_spec(raw),
                                          day, turn, number, store)
                         for key, raw in blocks.items()}
    return out


def masthead_copy(persona: dict, day: Date,
                  voice: "narrator.Narration | None" = None) -> dict[str, str]:
    """The persona's masthead lines ([persona.masthead]): the narrator's, or
    the day's fallback.

    Fallbacks are hand-written lists, index-aligned across the fields so a
    title keeps its own subtitle, and picked by date - a re-run of the same
    morning without the narrator prints the same lines. A field the narrator
    wrote is used as written; one it missed falls back on its own. A field
    whose wording depends on the day's variant gives `fallbacks`, one list per
    variant, instead of `fallback`.
    """
    spec = persona.get("masthead") or {}
    if not spec:
        return {}
    written = voice.masthead if voice is not None else {}
    variant = variant_of(persona, day)

    def pool(field: dict) -> list[str]:
        if "fallbacks" in field:
            return field["fallbacks"][variant % len(field["fallbacks"])]
        return field.get("fallback", [])

    lengths = [len(pool(f)) for f in spec.values()]
    pick = (random.Random(f"masthead:{persona['name']}:{day.isoformat()}")
            .randrange(min(lengths)) if all(lengths) else None)
    out = {}
    for key, field in spec.items():
        text = written.get(key) or (pool(field)[pick] if pick is not None
                                    else "")
        if text:
            out[key] = text
    return out


def encipher_masthead(persona: dict, lines: dict[str, str],
                      day: Date) -> tuple[dict[str, str], dict | None]:
    """Encipher one narrated masthead line for real ([persona.cipher]).

    The Revolutionary is the only persona that asks. The narrator writes the
    message in clear; Python enciphers it, adds the key and her explanation of
    it as two further lines the theme can set, and hands back the plaintext for
    the upside-down answers footer - which is the house rule for every puzzle on
    this machine (SLOTS.md, PUZZLES), and the reason the cipher can be a real
    one rather than a decorative squiggle: a reader who cannot be bothered has
    the answer on the same page, the wrong way up.

    Which cipher is the theme's variant, so consecutive mornings are not the
    same puzzle. Returns the lines with the field replaced, and the answer.
    """
    spec = persona.get("cipher")
    if not spec or spec["field"] not in lines:
        return lines, None
    sent = ciphers.encipher(lines[spec["field"]], day,
                            ciphers.kind_for(variant_of(persona, day)))
    if sent is None:                       # nothing enciphrable: send it clear
        return lines, None
    out = {}
    for key, text in lines.items():
        out[key] = sent.text if key == spec["field"] else text
        if key == spec["field"]:
            out[f"{key}-key"] = sent.key_line
            out[f"{key}-note"] = sent.note
    return out, {"label": spec.get("label", "IN CLEAR"), "answer": sent.plain}


def dialogue(text: str, speakers: list[str]) -> str:
    """Set a narrated exchange as a transcript ([persona] speakers).

    A persona whose sections are dialogue - the Commentary Box's two men - is
    told to write each turn as NAME: line. Where a body does that, each turn
    becomes its own block with the name in a span a theme can set as a column.
    Anything else is left exactly as written: an unvoiced fallback, a body with
    no named turns, or a name the persona does not declare, so a stray capital
    word and a colon can never be mistaken for a speaker.
    """
    names = "|".join(re.escape(n.upper()) for n in speakers)
    parts = re.split(rf"(?:^|\s+)({names}):\s*", text.strip())
    if len(parts) < 3 or parts[0].strip():
        return text
    turns = list(zip(parts[1::2], parts[2::2]))
    return "".join(
        f'<span class="turn"><span class="spk">{html.escape(name.strip())}</span>'
        f'<span class="said">{html.escape(said.strip())}</span></span>'
        for name, said in turns)


def asides(text: str) -> str:
    """Mark a persona's bracketed asides so a theme can set them ([persona] asides).

    One persona asks questions in brackets in the middle of everything it writes,
    and those questions are the only moment on its page that is its own rather
    than the persona it is wearing - so they have to LOOK like it, and a theme
    cannot reach a substring of a narrated sentence on its own.

    Same shape as `dialogue()` above: Python finds what the narrator was told to
    write and wraps it, rather than the narrator being trusted to emit markup.
    Nested brackets are left alone, and so is anything longer than a sentence or
    two - a whole paragraph in brackets is not an aside, it is a mistake, and
    setting it in a second face would wreck the section.
    """
    return re.sub(r"\(([^()]{3,180}?)\)", r'<span class="aside">(\1)</span>', text)


# A masthead line that names its own heading: "EQUIPMENT: Gloves you will
# regret not having." Capitals only, and short, so an ordinary sentence that
# happens to contain a colon is never mistaken for one.
LABELLED_LINE = re.compile(r"^([A-Z][A-Z0-9 /'()-]{1,15}):\s+(\S.*)$")


def masthead_html(lines: dict[str, str], speakers: list[str] | None,
                  labelled: bool = False) -> dict[str, str]:
    """The masthead's own lines, ready to drop into the page.

    The template does not escape these, because a persona with `speakers` may
    have written its head as an exchange and that has to reach the page as
    markup - so the escaping happens here instead, once, on whichever half of
    each line is plain text: `dialogue()` escapes every turn it sets, and
    anything it leaves alone is escaped on the way out.

    `[persona] masthead_label_lines` adds the other shape: a line whose heading
    the narrator chose rather than the stylesheet. OPS's orders need it - the
    three paragraphs under the mission are EQUIPMENT one day and EXFIL the next,
    because they are supposed to follow from the mission, and a heading fixed in
    CSS cannot do that. Off by default: a stylesheet that is not expecting
    `.mh-label` would print the heading as a run of capitals in the middle of
    the sentence.
    """
    out = {}
    for key, text in (lines or {}).items():
        marked = LABELLED_LINE.match(text) if labelled else None
        if marked:
            out[key] = (f'<span class="mh-label">{html.escape(marked[1])}</span>'
                        f'<span class="mh-text">{html.escape(marked[2])}</span>')
            continue
        set_as_turns = dialogue(text, speakers) if speakers else text
        out[key] = (set_as_turns if set_as_turns != text
                    else html.escape(text))
    return out


def build_html(day: Date, persona: dict, spine: dict,
               rotating: list[dict], receipt_no: int, body_px: int | None,
               masthead: dict[str, str] | None = None,
               answers_extra: list[dict] | None = None) -> str:
    body, small, tiny = sizes(persona["font"])
    if body_px is not None:
        body, small, tiny = body_px, body_px - 2, body_px - 4

    # Spine has no rarity tier, so it is not itemised - the itemization is a
    # record of what was *drawn*, and the spine is never drawn.
    lines = [{"name": s["name"].upper(), "tier": s["tier"],
              "price": PRICE[s["tier"]]}
             for s in rotating if s["tier"] in PRICE]

    # Puzzle solutions, printed the same day and upside-down (SLOTS.md, PUZZLES).
    # Built after narration so each one is labelled with the header the persona
    # actually chose - "SOLUTION: Nonogram" would leak the internal slot name
    # that persona bleed exists to keep off the paper.
    answers = [{"label": s["head"], "answer": s["answer"]}
               for s in rotating if s.get("answer")]
    # A persona may put something there too - the Revolutionary's enciphered
    # transmission, which is a puzzle like any other and obeys the same rule.
    answers += answers_extra or []
    subtotal = sum(x["price"] for x in lines)
    filled = min(5, 1 + sum(t != "common" for t in (x["tier"] for x in lines)))
    stars = "★" * filled + "☆" * (5 - filled)

    # The display and accent faces. Unlike the body face these are optional: one
    # that is not in the manifest is skipped and the theme falls back to the
    # body, since a missing heading face should never cost the morning.
    fonts = persona.get("fonts", {})
    # "own" is a third role and exists for one persona: the Mimic borrows every
    # other face from whoever it is wearing, and needs one face that is not
    # borrowed, for the single line a morning where the disguise drops. Any
    # persona may declare it; only a theme that asks for var(--font-own) uses it.
    extra = {role: fonts[role] for role in ("display", "accent", "own")
             if fonts.get(role) in manifest()}
    families = dict.fromkeys([persona["font"], *extra.values()])
    # Some display faces only read at one weight - Doto is a hairline below 900.
    display_weight = fonts.get("display_weight", 400) if "display" in extra else 400

    # Tonight's moon as one of eight phases, 0 new to 4 full, for a theme that
    # draws one. Computed, like slot 37 - a persona may decorate the sky but
    # never gets to choose it.
    from slots.moon import phase
    moon = round(phase(day)[0] * 8) % 8
    variant = variant_of(persona, day)

    weather = weather_block(spine, persona)
    coupon = coupon_block(spine, persona)
    legalese = legalese_block(spine, persona)
    # The persona's own bracketed asides, marked for the theme. After dialogue,
    # so a page that is both a transcript and full of asides gets both.
    def voiced(text):
        return asides(text) if persona.get("asides") else text

    speakers = persona.get("speakers")
    if speakers:
        if weather:
            weather["verdict"] = dialogue(weather["verdict"], speakers)
        # The small print too: the narrator writes it now, and the Commentary
        # Box's legalese footnote is the last word one of them gets in.
        if coupon:
            coupon["body"] = dialogue(coupon["body"], speakers)
            if coupon.get("terms"):
                coupon["terms"] = dialogue(coupon["terms"], speakers)
        if legalese:
            legalese["body"] = dialogue(legalese["body"], speakers)
            if legalese.get("footnote"):
                legalese["footnote"] = dialogue(legalese["footnote"], speakers)
        rotating = [dict(s, body=dialogue(s["body"], speakers))
                    if isinstance(s.get("body"), str)
                    and not (s.get("brief") or {}).get("verbatim") else s
                    for s in rotating]

    if persona.get("asides"):
        if weather:
            weather["verdict"] = voiced(weather["verdict"])
        for block, fine in ((coupon, "terms"), (legalese, "footnote")):
            if not block:
                continue
            block["body"] = voiced(block["body"])
            if block.get(fine):
                block[fine] = voiced(block[fine])
            # A block set as lines is escaped already (`block_lines`); its
            # asides are marked line by line, after that.
            for line in block.get("lines") or []:
                line["text"] = voiced(line["text"])
        # Never a verbatim body: those are shapes rather than sentences, and a
        # bracket in a drawing is part of the drawing (CLAUDE.md invariant 9).
        rotating = [dict(s, body=voiced(s["body"]))
                    if isinstance(s.get("body"), str)
                    and not (s.get("brief") or {}).get("verbatim") else s
                    for s in rotating]

    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")),
                      autoescape=False)
    return env.get_template("receipt.html.j2").render(
        font_face_css="".join(face_css(f) for f in families) + mono_face_css(),
        font_stack=stack(persona["font"]),
        font_display=stack(extra["display"]) if "display" in extra else None,
        font_accent=stack(extra["accent"]) if "accent" in extra else None,
        display_weight=display_weight,
        accent_bold=bold_weight(extra["accent"]) if "accent" in extra else None,
        font_own=stack(extra["own"]) if "own" in extra else None,
        own_bold=bold_weight(extra["own"]) if "own" in extra else None,
        font_mono=mono_stack(),
        bold_weight=bold_weight(persona["font"]),
        size_body=body, size_small=small, size_tiny=tiny,
        theme_css=theme_css(persona),
        reader=css_string(config.reader_name()),
        reader_caps=css_string(config.reader_name().upper()),
        wordmark=persona.get("display", "Quick-Guthe"),
        dateline=f"{day:%A, %d %B %Y}",
        weather=weather,
        news=news_block(spine, persona),
        slots=[s for s in rotating if not s.get('absorbed')],
        coupon=coupon,
        legalese=legalese,
        tear_glyph=persona.get("tear_glyph", "* * *"),
        itemization={"lines": lines, "subtotal": subtotal},
        answers=answers,
        stars=stars,
        receipt_no=f"{receipt_no:04d}",
        moon=moon,
        variant=variant,
        wet=int(bool(weather and weather.get("wet"))),
        roll_pct=round(
            (persona.get("history", {}).get("paper_mm_all", 0) % ROLL_MM)
            / ROLL_MM * 100),
        # Which appearance this is, for a persona told its history - the
        # Machine numbers its firmware by it. Counted from the receipts, so the
        # first morning it ever printed is 1.
        appearance=(persona["history"]["appearances"] + 1
                    if persona.get("history") else None),
        # A real photograph for a masthead that runs one ([persona.picture]),
        # dithered before it got here (CLAUDE.md invariant 2).
        picture=persona.get("picture_today"),
        # A share price for a persona that runs one ([persona.stock]): the
        # close is this receipt's subtotal, so it is computed here, after any
        # slot the budget dropped (render_within_budget rebuilds through here).
        stock=(stock_panel(persona["stock_today"], subtotal)
               if persona.get("stock_today") else None),
        masthead_copy={k: voiced(v) for k, v in masthead_html(
            masthead if masthead is not None else masthead_copy(persona, day),
            speakers, persona.get("masthead_label_lines", False)).items()},
        serial_date=f"{day:%d %b %Y}".upper(),
        month_no=f"{day:%m}",
        # Whom the Mimic is wearing, for the overlay stylesheet: a mistake that
        # works on one borrowed theme can be wrong on another, and this is the
        # only way a stylesheet can tell which coat it is on top of.
        wears=persona.get("wears", ""),
        # Which masthead fields swallowed a slot today (`absorb`), so the theme
        # can set that one at the scale of a section rather than a line.
        absorbed=" ".join(persona.get("absorbed") or []),
        barcode=img_tag(code39(f"{day:%Y%m%d}", width=WIDTH_DOTS, height=30)),
    )


def render_within_budget(renderer, html: str, threshold: int | None, day: Date,
                         persona: dict, spine: dict, rotating: list[dict],
                         number: int, body_px: int | None,
                         masthead: dict[str, str] | None = None,
                         answers_extra: list[dict] | None = None):
    """Render, and if the page overflows, drop the biggest slot and try again.

    The last line of defence for invariant 1. Budget fitting works from
    `SlotSpec.paper_mm`, which is an estimate made before anything is fetched -
    a poem does not know which poem it is yet, a painting does not know its
    aspect ratio. The estimates are worst-case (`tools/papercheck.py` keeps them
    honest), but "worst case" is a claim about today, not a proof about every
    day, and the alternative to this is a stack trace instead of a receipt at
    seven in the morning.

    Drops the largest rotating slot each time, because that is the one most
    likely to be the cause and the one whose absence costs least.
    """
    dropped: list[int] = []
    for _ in range(len(rotating) + 1):
        try:
            return renderer.render(html, threshold=threshold), dropped
        except BudgetExceeded:
            if not rotating:
                raise
            fattest = max(rotating, key=lambda s: len(s.get("body") or "")
                          + (400 if s.get("image") else 0))
            rotating.remove(fattest)
            dropped.append(fattest["id"])
            html = build_html(day, persona, spine, rotating, number, body_px,
                              masthead, answers_extra)
    raise RuntimeError("could not fit the receipt into the paper budget")


@dataclass
class Morning:
    """One day as rendered: what was drawn, what was written, what came out.

    `render_day` makes one and everything after the render reads it - the
    summary, the paper, the record - so a real morning and each column of the
    contact sheet are the same pipeline rather than two that drift apart.
    """
    day: Date
    persona: dict
    number: int
    draw: "selection.Draw"
    spine: dict
    rotating: list[dict]
    failures: list[SlotFailure]
    occasion: object | None
    fmt: "legendary.Format | None"
    voice: "narrator.Narration | None"
    pages: list
    dropped: list[int]
    rehearsal: bool

    @property
    def img(self):
        return self.pages[0]


def render_day(day: Date, store: Store, personas: dict, *,
               forced: str | None = None, wears: str | None = None,
               offline: bool = False, may_narrate: bool = True,
               real: bool = False, printed_already: bool = False,
               threshold: int | None = None, body_px: int | None = None,
               forced_legendary: str | None = None,
               renderer: Renderer | None = None) -> Morning:
    """One morning, from the persona draw to the rendered pages.

    Everything short of the paper: persona, slots, legendary, narrator, layout
    and render. What happens to the pages, and whether the day is remembered,
    is the caller's (`main`, `contact_sheet`) - nothing here records a
    receipt.

    `real` is whether the caller is running a real morning, and an audition
    never is one whatever the caller says (`Morning.rehearsal`). A `renderer`
    is reused when given, which is how the contact sheet puts thirty days
    through one browser; without one, a browser opens for this page alone,
    once the narrator has answered.
    """
    persona = pick_persona(personas, day, forced, store)
    # The Mimic is dressed before anything else reads it: the disguise changes
    # its faces, its stylesheet, its section names and its variant count, and
    # everything downstream - the narrator above all - has to see the costume
    # rather than the creature.
    persona = mimicry(persona, personas, day, store, wears)
    persona = for_the_day(persona, day, store)
    # An audition is a rehearsal: rendered and narrated like any morning, never
    # remembered. Recording one would put a persona that has not debuted into
    # the continuity digest, and the regulars would start feuding with it.
    rehearsal = bool(persona.get("audition"))

    persona = with_history(persona, store)
    persona = with_stock(persona, store, day)
    ctx = Context(date=day, store=store, offline=offline)
    # Slots that want to suit the day's persona read it from here. The
    # persona is drawn first, so it is available before any slot runs.
    ctx.shared["persona_art_tags"] = persona.get("art_tags", [])
    ctx.shared["persona_name"] = persona["name"]
    # Slots that make their own model call (151, the persona's object) obey the
    # same switches as the main narrator.
    ctx.shared["may_narrate"] = may_narrate
    # Whether this run is a real morning. Slots that write lasting state - a pin
    # promising tomorrow's continuation, above all - check this, because a
    # --date simulation that pinned a recipe for a real future date would one
    # day print the second half of a meal that was never started.
    ctx.shared["real_morning"] = real and not rehearsal
    # A preview after today's receipt printed: the morning is real, but what
    # it remembers must stay what was on the paper (the rule `save_receipt`
    # follows in `main`). Slots that remember what they printed check this.
    ctx.shared["printed_already"] = printed_already

    spine, rotating, failures, draw = gather(ctx)

    # One-day-only occasions bypass the draw entirely (SYSTEM.md 4): on the
    # day they print, and on no other day can they.
    from slots.occasions import OneDayOnly
    occasion = safe_fetch(OneDayOnly(), ctx, failures)
    if occasion is not None:
        rotating.insert(0, {
            "id": 118, "tier": "legendary", "name": "One-day-only slots",
            "head": occasion.head, "body": occasion.body, "image": None,
            "fine": occasion.fine, "answer": None, "brief": occasion.brief,
            "needs_narrator": True, "needs_search": False})

    # A persona whose masthead swallows one of the day's slots takes it here,
    # after the occasion is in and before anything is narrated or laid out.
    persona = absorb(persona, rotating)

    number = store.receipt_number_for(day)

    # Legendary: a hit on the roll, or forced from the command line (an unknown
    # key is turned away in `main`, before anything is fetched).
    fmt = None
    if forced_legendary:
        fmt = (legendary.choose(store, day, record=False)
               if forced_legendary == "any" else legendary.by_key(forced_legendary))
    elif draw.legendary:
        fmt = legendary.choose(store, day, record=ctx.shared["real_morning"])
    lctx = legendary.Context(day=day, persona=persona, store=store,
                             rotating=rotating, number=number,
                             real_morning=ctx.shared["real_morning"],
                             may_narrate=may_narrate)

    voice = None
    page = None
    if fmt is not None and fmt.replaces_page:
        try:
            page = fmt.page(lctx)
        except Exception as exc:  # noqa: BLE001 - the ordinary receipt still prints
            print(f"  legendary {fmt.key} failed ({exc}); printing ordinary receipt")
            fmt, page = None, None
    if page is None:
        # Fetched before narration: the caption under it is narrated from what
        # the photograph really shows.
        persona = with_picture(persona, day, store, offline)
    if page is None and may_narrate:
        voice = narrate(day, persona, spine, rotating, store,
                        record=ctx.shared["real_morning"])
    block_fallbacks(persona, spine, set(voice.bodies) if voice else set(), day)

    if page is not None:
        html = page
    else:
        masthead = masthead_copy(persona, day, voice)
        masthead, sent = encipher_masthead(persona, masthead, day)
        html = build_html(day, persona, spine, rotating, number, body_px,
                          masthead, [sent] if sent else None)
        if fmt is not None and fmt.css:
            html = html.replace("</style></head>", fmt.css + "</style></head>", 1)

    with (nullcontext(renderer) if renderer is not None else Renderer()) as r:
        if page is not None:
            # Legendary pages keep their blank space and are allowed past the
            # budget: both are deliberate, and the ceiling is for ordinary
            # mornings (render/page.py).
            img = r.render(html, threshold=threshold, trim=False,
                           strict_budget=False)
            dropped = []
        else:
            img, dropped = render_within_budget(r, html, threshold, day,
                                                persona, spine, rotating, number,
                                                body_px, masthead,
                                                [sent] if sent else None)
        # Extra copies are rendered from the final page, after any budget drops,
        # so a duplicate is genuinely identical to the original.
        pages = [img]
        if fmt is not None:
            extra = fmt.variants(html, lctx)[1:]
            pages += [r.render(v, threshold=threshold, strict_budget=False)
                      for v in extra]
    if fmt is not None:
        try:
            pages = [fmt.transform(p, lctx) for p in pages]
        except Exception as exc:  # noqa: BLE001
            print(f"  legendary transform failed ({exc}); printing untransformed")

    return Morning(day=day, persona=persona, number=number, draw=draw,
                   spine=spine, rotating=rotating, failures=failures,
                   occasion=occasion, fmt=fmt, voice=voice, pages=pages,
                   dropped=dropped, rehearsal=rehearsal)


def report(m: Morning) -> None:
    """The run's summary on the console: what printed, and what did not."""
    if m.dropped:
        print(f"  dropped for budget at render time: {m.dropped}")
    print(f"{m.day}  {m.persona['name']:<16} {len(m.rotating)} slots  "
          f"{m.img.width}x{m.img.height}px ({m.img.height / 8:.0f}mm)")
    print(f"  draw: {'/'.join(m.draw.tiers) or 'none'}  "
          f"{selection.miss_line(m.draw)} ({m.draw.roll_source})")
    if m.draw.skipped_for_budget:
        print(f"  skipped for budget: {m.draw.skipped_for_budget}")
    for f in m.failures:
        print(f"  dropped #{f.slot_id} {f.name}: {f.error}")
    voice = m.voice
    if voice is not None:
        searched = ""
        if voice.searches:
            searched = (f"  {voice.searches} web search"
                        f"{'es' if voice.searches != 1 else ''}"
                        + (" (ERRORED)" if voice.search_failed else ""))
        print(f"  narrator: {voice.model}  {voice.input_tokens}in/"
              f"{voice.output_tokens}out  ${voice.cost_usd:.4f}  "
              f"{len(voice.headers)} headers, {len(voice.bodies)} bodies"
              f"{searched}")
    else:
        print("  narrator: templated copy")

    if m.fmt is not None:
        print(f"  LEGENDARY: {m.fmt.name} (4.1 #{m.fmt.spec_number})"
              + (f", {len(m.pages)} copies" if len(m.pages) > 1 else ""))
    if m.occasion is not None:
        print(f"  one day only: {', '.join(m.occasion.brief['occasions'])}")


# What each recorded morning said, keyed by ISO date (`printed_text`).
PRINTED_TEXT = "receipt:text"


def _plain_text(markup: str | None) -> str:
    """A section's body as the words on the paper: tags out, entities decoded.

    A drawing - an SVG, a grid of boxes - has no words and comes out empty,
    which is said rather than left blank.
    """
    if not markup:
        return ""
    text = re.sub(r"<(svg|style|script)\b.*?</\1>", " [drawing] ", markup,
                  flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</?(div|p|li|tr)\b[^>]*>", "\n", text,
                  flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def printed_text(m: Morning) -> dict:
    """The morning's words, section by section, in page order.

    What `remember` keeps so that feedback on a morning can be checked against
    what it actually said - the receipts row only knows which slots printed.
    """
    def section(sid: int, name: str, head, body, fine) -> dict:
        return {"id": sid, "name": name, "head": _plain_text(head),
                "body": _plain_text(body), "fine": _plain_text(fine)}

    sections = [section(sid, get(sid).spec.name, r.head, r.body, r.fine)
                for sid, r in m.spine.items()]
    sections += [section(i["id"], i["name"], i.get("head"), i.get("body"),
                         i.get("fine"))
                 for i in m.rotating]
    return {"persona": m.persona["name"],
            "wears": m.persona.get("wears"),
            "legendary": m.fmt.name if m.fmt is not None else None,
            "masthead": masthead_copy(m.persona, m.day, m.voice),
            "narrated": m.voice is not None,
            "sections": sections}


def remember(store: Store, m: Morning, keep_page: bool = True) -> None:
    """Save the morning's row: who wore it, what was drawn, what it cost - and
    what it said, with the page itself kept beside it.

    The contact sheet records into a scratch store and passes `keep_page`
    False: the store copy goes when it closes, and a file would not.
    """
    rarity: dict[str, int] = {}
    for item in m.rotating:
        rarity[item["tier"]] = rarity.get(item["tier"], 0) + 1
    store.save_receipt(
        m.day, m.number, m.persona["name"],
        sorted(list(m.spine) + [i["id"] for i in m.rotating]),
        rarity, round(m.img.height / 8),
        api_cost=m.voice.cost_usd if m.voice else 0.0)
    # The record of what printed is a convenience: neither half of it is worth
    # failing a morning that has already gone to paper.
    try:
        store.put(PRINTED_TEXT, m.day.isoformat(), printed_text(m), when=m.day)
    except Exception as exc:  # noqa: BLE001
        print(f"  page text not kept ({exc})")
    if not keep_page:
        return
    try:
        archive = config.path("paths", "archive")
        archive.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(m.pages):
            page.save(archive / (f"{m.day.isoformat()}.png" if i == 0
                                 else f"{m.day.isoformat()}-copy{i}.png"))
    except Exception as exc:  # noqa: BLE001
        print(f"  page image not archived ({exc})")


# The contact sheet (ROADMAP, Verification): N simulated mornings side by side,
# for eyeballing persona rotation and the rarity mix at once. Each receipt is a
# third of its width - NEAREST, never smoothed, so what shrinks is the real bit
# pattern rather than a grey impression of it - and the days wrap a week to a
# row, so the same face twice inside a week sits in one row. Tops align, so the
# row also shows which mornings ran long.
SHEET_SCALE = 3
SHEET_WEEK = 7
SHEET_GAP = 16
SHEET_GREY = 0xC0          # the preview's surround, so every paper edge shows
SHEET_FONT_PX = 13
# After a slot id on a label: rarity at a glance, the way mixcheck strips it.
TIER_MARK = {"common": "", "uncommon": "+", "rare": "*", "legendary": "!"}


def sheet_label(m: Morning) -> list[str]:
    """A column's caption: the date, who wore it, what was drawn and its length."""
    who = m.persona["name"] + (f" as {m.persona['wears']}"
                               if m.persona.get("wears") else "")
    lines = [f"{m.day:%a %d %b %Y}".upper(), who,
             f"{m.img.height / 8:.0f}mm, {m.persona.get('rarity', 'common')} persona",
             " ".join(f"#{s['id']}{TIER_MARK.get(s['tier'], '?')}"
                      for s in m.rotating) or "no slots"]
    if m.fmt is not None:
        lines.append(f"LEGENDARY: {m.fmt.name}")
    if m.dropped or m.failures:
        lines.append("dropped " + " ".join(
            f"#{sid}" for sid in [*m.dropped, *(f.slot_id for f in m.failures)]))
    return lines


def lay_out_sheet(columns: list[tuple[list[str], Image.Image | None]],
                  header: list[str]):
    """The columns on one canvas, a week to a row, captioned and headed."""
    files = manifest()[MONO_FAMILY]
    face = next((f for f in files if f.endswith("-700.woff2")), files[0])
    font = ImageFont.truetype(str(FONT_DIR / face), SHEET_FONT_PX)
    line_h = round(SHEET_FONT_PX * 1.4)
    col_w = max([WIDTH_DOTS // SHEET_SCALE]
                + [img.width for _, img in columns if img is not None])
    chars = max(8, int(col_w // font.getlength("M")))
    captions = [[part for line in label
                 for part in textwrap.wrap(line, chars) or [""]]
                for label, _ in columns]

    per_row = min(SHEET_WEEK, len(columns))
    width = per_row * col_w + (per_row + 1) * SHEET_GAP
    head_w = max(8, int((width - 2 * SHEET_GAP) // font.getlength("M")))
    head = [part for line in header for part in textwrap.wrap(line, head_w)]
    top = SHEET_GAP + len(head) * line_h + SHEET_GAP

    rows = [range(i, min(i + per_row, len(columns)))
            for i in range(0, len(columns), per_row)]
    heights = []
    for row in rows:
        cap = max(len(captions[i]) for i in row) * line_h
        tall = max((columns[i][1].height for i in row
                    if columns[i][1] is not None), default=0)
        heights.append((cap, tall))
    height = top + sum(cap + SHEET_GAP // 2 + tall + SHEET_GAP
                       for cap, tall in heights)

    sheet = Image.new("L", (width, height), SHEET_GREY)
    pen = ImageDraw.Draw(sheet)
    for n, line in enumerate(head):
        pen.text((SHEET_GAP, SHEET_GAP + n * line_h), line, fill=0, font=font)
    y = top
    for row, (cap, tall) in zip(rows, heights):
        for j, i in enumerate(row):
            x = SHEET_GAP + j * (col_w + SHEET_GAP)
            for n, line in enumerate(captions[i]):
                pen.text((x, y + n * line_h), line, fill=0, font=font)
            img = columns[i][1]
            if img is not None:
                sheet.paste(img, (x, y + cap + SHEET_GAP // 2))
        y += cap + SHEET_GAP // 2 + tall + SHEET_GAP
    return sheet


def contact_sheet(args) -> int:
    """`--contact-sheet N`: N simulated mornings from `--date` (or today), side
    by side in one PNG.

    Every day is a simulation, like a `--date` run, and offline whatever was
    asked: fixtures and the cache, no network and no narrator, so thirty days
    cost nothing. Nothing is recorded - no receipt, no pin, no news memory, no
    legendary used up. The days run against a scratch copy of the store
    (`Store.scratch`) and each is saved into the copy, so tomorrow's draw is
    damped by today's the way a real month would be - the reason
    `tools/mixcheck.py` keeps an archive of its own - and the copy goes at the
    end. The first page alone is shown for a legendary that prints copies.
    """
    start = args.date or Date.today()
    personas = load_personas(auditions=args.persona is not None)
    store = Store.scratch(config.path("paths", "cache"))
    columns: list[tuple[list[str], Image.Image | None]] = []
    mornings: list[Morning] = []
    try:
        with Renderer() as r:
            for i in range(args.contact_sheet):
                day = start + timedelta(days=i)
                try:
                    m = render_day(day, store, personas, forced=args.persona,
                                   wears=args.wears, offline=True,
                                   may_narrate=False, threshold=args.threshold,
                                   body_px=args.body,
                                   forced_legendary=args.legendary, renderer=r)
                except Exception as exc:  # noqa: BLE001 - one bad day is one column
                    print(f"{day}  FAILED  {type(exc).__name__}: {exc}")
                    columns.append(([f"{day:%a %d %b %Y}".upper(), "FAILED",
                                     f"{type(exc).__name__}: {exc}"[:160]], None))
                    continue
                remember(store, m, keep_page=False)
                mornings.append(m)
                label = sheet_label(m)
                print(f"{day}  {label[1]:<26} {label[2]:<24} {label[3]}"
                      + "".join(f"  {extra}" for extra in label[4:]))
                for f in m.failures:
                    print(f"    dropped #{f.slot_id} {f.name}: {f.error}")
                small = m.img.convert("L").resize(
                    (m.img.width // SHEET_SCALE, m.img.height // SHEET_SCALE),
                    Image.NEAREST)  # never smooth - it would hide dropped pixels
                columns.append((label, small))
    finally:
        store.close()

    n = len(mornings)
    tiers = [{s["tier"] for s in m.rotating} for m in mornings]
    faces = [m.persona["name"] for m in mornings]
    tally = (f"{n} rendered: uncommon or better on "
             f"{sum(bool(t & {'uncommon', 'rare', 'legendary'}) for t in tiers)}, "
             f"a rare on {sum('rare' in t for t in tiers)}, "
             f"a legendary format on {sum(m.fmt is not None for m in mornings)}; "
             f"{len(set(faces))} persona{'s' if len(set(faces)) != 1 else ''}, "
             f"the same face twice running "
             f"{sum(a == b for a, b in zip(faces, faces[1:]))} times")
    header = [f"CONTACT SHEET - {args.contact_sheet} mornings from "
              f"{start:%a %d %b %Y}, simulated offline, nothing recorded",
              "#id common   #id+ uncommon   #id* rare   #id! legendary   "
              f"(receipts at 1/{SHEET_SCALE}, a week to a row)", tally]
    print(f"\n  {tally}")
    sheet = lay_out_sheet(columns, header)
    out = Path(args.out or "out/contact-sheet.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"contact sheet -> {out}  ({sheet.width}x{sheet.height}px, "
          f"{len(columns)} days)")
    return 0 if n == len(columns) else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="render to PNG")
    ap.add_argument("--dry-run", action="store_true", help="build, print nothing")
    ap.add_argument("--date", type=Date.fromisoformat, default=None)
    ap.add_argument("--persona", default=None)
    ap.add_argument("--wears", default=None, metavar="PERSONA",
                    help="whom the Mimic impersonates, instead of whoever "
                         "printed last")
    ap.add_argument("--offline", action="store_true", help="fixtures only")
    ap.add_argument("--no-narrator", action="store_true",
                    help="skip the Claude call; templated copy only")
    ap.add_argument("--threshold", type=int, default=None)
    ap.add_argument("--body", type=int, default=None)
    ap.add_argument("--out", default=None,
                    help="the PNG to write (default out/receipt.png, or "
                         "out/contact-sheet.png)")
    ap.add_argument("--legendary", default=None, metavar="FORMAT",
                    help="force a legendary format by key, or 'any' to draw one "
                         f"({', '.join(f.key for f in legendary.BUILT)})")
    ap.add_argument("--contact-sheet", type=int, default=None, metavar="N",
                    help="render N simulated days from --date (or today) side by "
                         "side in one PNG; always offline, never printed, never "
                         "recorded")
    args = ap.parse_args()
    if args.contact_sheet is not None and args.contact_sheet < 1:
        ap.error("--contact-sheet needs at least one day")

    if config.location_is_placeholder():
        print("NOTE: location is still the London placeholder. "
              "Set QG_LATITUDE / QG_LONGITUDE in .env.", file=sys.stderr)
    if args.legendary not in (None, "any") and legendary.by_key(args.legendary) is None:
        print(f"unknown legendary format {args.legendary!r}", file=sys.stderr)
        return 2
    if args.contact_sheet is not None:
        return contact_sheet(args)

    day = args.date or Date.today()
    # Forcing a persona may reach into the auditions; the draw never does.
    personas = load_personas(auditions=args.persona is not None)
    # The store opens here rather than below because the draw reads it: the
    # recency curve needs to know who printed lately.
    store = Store(config.path("paths", "cache"))
    m = render_day(
        day, store, personas, forced=args.persona, wears=args.wears,
        offline=args.offline, may_narrate=not (args.no_narrator or args.offline),
        real=not args.dry_run and (args.date is None or args.date == Date.today()),
        printed_already=bool(args.preview and store.has_receipt(day)),
        threshold=args.threshold, body_px=args.body,
        forced_legendary=args.legendary)
    report(m)

    if args.dry_run:
        pass
    elif args.preview:
        out_path = args.out or "out/receipt.png"
        for i, p in enumerate(m.pages):
            out = out_path if i == 0 else out_path.replace(".png", f"-copy{i}.png")
            get_printer("preview", path=out, scale=2).print_image(p)
    else:
        printer = get_printer("usb")
        for p in m.pages:
            printer.print_image(p)
        print(f"  sent to printer{f' ({len(m.pages)} copies)' if len(m.pages) > 1 else ''}")

    # Record the morning - but only a real one.
    #
    # A --date run is a simulation, and recording it would make the machine
    # remember mornings that never happened, which then feed the narrator's
    # continuity digest as if they had. --dry-run explicitly builds nothing.
    # A preview of *today* does count: the day happened, and the row is keyed by
    # day so a later real print replaces it rather than duplicating. It may not
    # go the other way, though - the row an evening preview would replace is
    # this morning's real receipt, with its persona, its slots and what it cost,
    # none of which the preview knows.
    simulated = args.date is not None and args.date != Date.today()
    already = args.preview and store.has_receipt(day)
    if m.rehearsal:
        print(f"  not recorded ({m.persona['name']} is in audition)")
    elif already:
        print("  not recorded (a preview never overwrites a printed morning)")
    elif not args.dry_run and not simulated:
        remember(store, m)
        print(f"  recorded no.{m.number:04d}  "
              f"({store.receipt_count()} receipts on file)")
    elif simulated:
        print("  not recorded (simulated date)")

    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
