"""Slot 151 - The persona's printed object.

Each morning it is drawn, the day's persona designs one small printed thing from
scratch - a dog tag, a playbill, a cheque for nothing, a treasure map to the
kraken - and writes it, in its own voice and its own visual style. What the
object *is* comes from that persona's own list in `assets/objects.toml`, so the
ops officer makes dog tags and redacted intel and the diner makes menus for
impossible food; how it looks is entirely the model's.

**Instructions, not a validator.** The model is told the printer's physical
limits - the width, a height cap, pure black and white, nothing under 12px, no
synthesised bold, only the fonts already on the page - and otherwise left
alone. If it ignores them the object prints badly or the section drops, which is
a worse morning, not a broken machine. Three things are structural rather than
design rules, and are enforced: its CSS is wrapped in `@scope` so it cannot
restyle the rest of the receipt, scripts are removed, and the object is clipped
at the height cap so it cannot run a metre.

**Its own call** (`narrator.design`), because it returns markup, and the main
narrator's contract is plain sentences. It is skipped under `--offline` and
`--no-narrator`, where the section drops.

**Mostly absurd.** Three objects in four go fully improbable; the rest are
played nearly straight with one detail wrong. Fabricated by design, and plainly
so - nothing on it could be taken for a real fact.
"""

from __future__ import annotations

import random
import re
import tomllib
from functools import lru_cache
from pathlib import Path

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

OBJECTS = Path(__file__).resolve().parent.parent / "assets" / "objects.toml"
NAMESPACE = "object151"
MAX_W = 540            # the section body is ~552px; a little room to spare
MAX_H = 760            # ~95mm, then clipped


@lru_cache(maxsize=1)
def catalogue() -> dict:
    return tomllib.loads(OBJECTS.read_text(encoding="utf-8"))


def items_for(persona: str) -> list[dict]:
    return (catalogue().get("persona", {}).get(persona, {}) or {}).get("items", [])


def pick(persona: str, used: list[str], rng: random.Random) -> dict | None:
    items = items_for(persona)
    fresh = [i for i in items if i["item"] not in used] or items
    if not fresh:
        return None
    return rng.choices(fresh, weights=[i.get("weight", 1) for i in fresh])[0]


def brief(item: str, absurd: bool, others: list[str]) -> str:
    cat = catalogue().get("absurd", {})
    examples = "; ".join(cat.get("examples", []))
    tone = (f"Go fully improbable and weird with it - the register of: {examples}."
            if absurd else
            "Play it nearly straight: a convincing object with exactly one "
            "detail that is quietly, badly wrong.")
    mimic = (f"\nOther personas who write on this machine: {', '.join(others)}."
             if others else "")
    return f"""Design and write ONE printed object: {item}.

{tone}{mimic}

It prints on a thermal receipt printer, inside one section of today's receipt.
Make it look like the real kind of object - its layout, borders, stamps,
perforations, fine print - designed in your own style.

Return `title` (the section header, in voice, a few words) and `html`: the
object as HTML with a single <style> block. The printer's limits:

- At most {MAX_W}px wide. Use width:100% or less; never a fixed width above that.
- At most {MAX_H}px tall - anything below is cut off.
- Pure black #000 and white #fff ONLY. No greys, no colours, no opacity, no
  shadows, no gradients except hard black/white stripes. A thermal head prints
  black or nothing; grey vanishes or turns into a solid slab.
- No text smaller than 12px. Body text reads best at 16-20px.
- Bold only as font-weight: var(--bold). Never a number - some faces have no
  bold and would be smeared.
- Fonts: var(--font), var(--font-display), var(--font-accent), var(--font-mono).
  Nothing else is loaded.
- No images, no external URLs, no scripts. Draw with CSS, borders, text, and
  inline <svg> with black strokes and fills.
- Lines thinner than 2px may not print. Solid black areas print well; white
  text on black needs to be large and bold.
- Keep the words short: it is read standing up over breakfast.

You have NO real data today - no weather, no news, no times, prices or figures
about the real world. Do not write any: an invented forecast on a receipt that
also prints the real one is a lie the reader cannot spot. Everything on the
object is openly made up, and should read that way."""


def _scoped(html: str) -> str:
    """The object's CSS confined to the object; scripts removed."""
    html = re.sub(r"(?is)<script\b.*?</script\s*>", "", html)
    styles = re.findall(r"(?is)<style\b[^>]*>(.*?)</style\s*>", html)
    body = re.sub(r"(?is)<style\b[^>]*>.*?</style\s*>", "", html)
    css = "\n".join(styles)
    return (f"<style>@scope (.obj151) {{ {css} }}</style>"
            f'<div class="obj151" style="max-width:{MAX_W}px;max-height:{MAX_H}px;'
            f'overflow:hidden;margin:4px auto 0">{body}</div>')


FIXTURE_HTML = """<style>
.tag { border: 4px solid #000; border-radius: 14px; overflow: hidden;
       text-align: center; width: 88%; margin: 0 auto; }
.tag-top { background: #000; color: #fff; padding: 8px 0 6px;
           font-family: var(--font-display); font-weight: var(--bold); }
.tag-top b { display: block; font-size: 44px; letter-spacing: .08em; }
.tag-name { font-family: var(--font-accent); font-size: 40px; padding: 26px 8px;
            transform: rotate(-4deg); }
.tag-foot { border-top: 2px dashed #000; font-size: 14px; padding: 6px; }
</style>
<div class="tag"><div class="tag-top"><b>HELLO</b>my name is</div>
<div class="tag-name">Dave? (not Dave)</div>
<div class="tag-foot">Agency temp - week 1 of 1 (week 9)</div></div>"""


@register
class PersonaObject(Slot):
    spec = SlotSpec(id=151, name="The persona's printed object", tier="common",
                    paper_mm=110, needs_network=True, needs_narrator=True)

    def _used(self, ctx: Context, persona: str) -> list[str]:
        if ctx.store is None:
            return []
        try:
            return list((ctx.store.fetch(NAMESPACE, "used", {}) or {}).get(persona, []))
        except Exception:  # noqa: BLE001
            return []

    def _remember(self, ctx: Context, persona: str, item: str) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        try:
            used = ctx.store.fetch(NAMESPACE, "used", {}) or {}
            seen = [i for i in used.get(persona, []) if i != item] + [item]
            if len(seen) >= len(items_for(persona)):
                seen = [item]             # list used up: start again
            used[persona] = seen
            ctx.store.put(NAMESPACE, "used", used)
        except Exception:  # noqa: BLE001
            pass

    def _result(self, title: str, html: str, item: str) -> SlotResult:
        return SlotResult(
            head=title or "Enclosed",
            body=_scoped(html),
            brief={"verbatim": True, "object": item,
                   "instruction": "Leave this section's header exactly as it "
                                  "is; the object was designed in voice already."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        if ctx.offline or not ctx.shared.get("may_narrate", True):
            return None
        name = ctx.shared.get("persona_name", "")
        rng = ctx.rng(self.spec.id)
        choice = pick(name, self._used(ctx, name), rng)
        if choice is None:
            return None
        import main
        import narrator
        personas = main.load_personas(auditions=True)
        persona = personas.get(name)
        if persona is None:
            return None
        others = ([p for p in personas if p != name]
                  if name == "mimic" else [])
        absurd = rng.random() < float(catalogue().get("absurd", {}).get("share", .75))
        out = narrator.design(ctx.date, persona, brief(choice["item"], absurd, others))
        if out is None:
            return None
        self._remember(ctx, name, choice["item"])
        return self._result(out.get("title", ""), out["html"], choice["item"])

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result("Name Badge (Mandatory)", FIXTURE_HTML,
                            "Name tag, filled in wrong")
