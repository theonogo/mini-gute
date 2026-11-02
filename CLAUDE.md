# quick-guthe

A thermal receipt printer (Epson TM-T20II, 80mm roll) that prints a personal
brief every morning.
Python owns the facts, Claude owns the voice, a rotating persona restyles the
page, and a rarity engine decides what lands each day.

## Read these first

| File | What it is |
|---|---|
| `docs/SYSTEM.md` | How the machine works — personas, rarity, series, input channel, failure handling |
| `docs/SLOTS.md` | What it prints — the full catalogue of ~90 slots |
| `docs/SLOT-STATUS.md` | What is *actually* built, how each slot works, what is outstanding on it |
| `docs/ROADMAP.md` | Current state and what is still open |

**Read `SLOTS.md` before touching any slot, and `SYSTEM.md` before touching the
selection engine, personas or the renderer.** Do not reconstruct a spec from
memory or from other slots — the details differ per slot and are deliberate.

## Invariants

These are not style preferences. Breaking one produces a bad morning.

1. **No collector raises into `main`.** Return a typed result or `None`. A dead
   source drops its slot or gets an in-character failure report — never a crash,
   never a blank page.
2. **Threshold text, dither photos, never in the same pass.** Images are dithered
   to pure 1-bit *before* being embedded in the HTML. The final page pass is a
   straight threshold. Dithering a composed page makes it unreadable.
3. **576px wide (72mm). Take the width from `printer.base.WIDTH_DOTS`**; never
   hardcode it. 576 dots is the head's native width on an
   80mm roll. The ~4mm of blank paper each side is unprintable, and **that is
   the margin** — design full-bleed to the full width and add no gutters of
   your own.
   **Length is not a design constraint.** The roll is 80 metres and costs
   pennies; the daily budget (`paper.budget_mm`, and `render.page.BUDGET_PX`
   behind it) is a guard against a runaway render, not a ration. Never trim a
   design, drop an element or shrink a persona's furniture to save millimetres,
   and never reach for brevity as a justification — if a page wants to be long,
   let it be long. Raise the budget instead. The only real limits are the width
   and the type floor.
4. **The width must be a multiple of 8.** Rows pack into whole bytes, so the
   raster stride is `ceil(width/8)` — take it from the image, never from the
   nominal width. A mismatch does not error; it prints as diagonal smear.
5. **Body 19px, small 17px, tiny 15px by default. Nothing goes below 12px,
   ever.** 12px is the measured hardware floor, never a body size
   (`docs/SYSTEM.md` §1.1–1.2). Many faces run larger - VT323 23/21/19, Archivo
   Narrow 26/24/22 - because nominal px is a poor guide to visual size, so sizes
   are set by measured characters-per-line (`tools/personafonts.py`), not by a
   uniform offset. The table lives in `render/fonts.py`.
   Take sizes from `render.fonts.sizes()`, never hardcode them in a theme, and
   never size type from a PIL preview — it reads a pixel more generously than
   Chromium does.
6. **Page threshold is 170, and reversed-out text is as bold as the face
   actually goes.** Both are measured, not taste (`docs/SYSTEM.md` §1.1). They
   pull opposite ways: ink rescues thin positive strokes and eats white-on-black
   glyphs. Use the `.inv` class so the weight is never forgotten.
   **Never synthesise a weight.** Several faces — VT323 and Special Elite among
   them — ship a 400 alone, and a browser asked for bold on those fakes it by
   smearing the glyph sideways: +50% ink and +60% stroke width for no extra
   drawn weight, and on reversed-out text the black smears *into* the counters.
   The base stylesheet sets `font-synthesis: none`; weights come from
   `var(--bold)`, never a literal 700. Where a face has no bold, emphasis comes
   from the layout — a bar, a rule, letter-spacing. `tools/boldtest.py` measures
   it. No greys, no opacity, anywhere.
7. **Slot IDs are stable.** They are the ones in `docs/SLOTS.md`. Never
   renumber, never reuse a cut ID.
8. **Marked invention.** Fabricated content (invented words, conspiracies) carries
   a consistent mark. Facts — weather, sky, search results, quotes, prices — are
   never embellished into inaccuracy, whatever the persona is doing around them.
9. **Markup in `body` means `verbatim` in `brief`.** A slot whose body is a
   shape rather than a sentence — an SVG, a grid, blank boxes — must set
   `brief["verbatim"] = True`. That removes the `body` field from the narrator's
   schema, so it *cannot* replace the drawing with a sentence. Without it the
   schema has a field, and a field eventually gets written into. If the body
   needs to be narrated, style it from the template instead (see `.slot-55`).

## Conventions

- **One slot = one collector + one template partial + a registry entry.** Adding
  a slot never edits central code. If it does, the registry is wrong.
- **Tier and `paper_mm` are config, not code.** A slot declares what
  `SLOTS.md` says; `[slots.tier]` / `[slots.paper_mm]` in `config.toml` override
  it at run time and `[slots] disabled` retires one. Read `slot.spec`
  everywhere; `slot.base_spec` is the declared version and exists only so the
  coverage report can tell a retuning from a doc mismatch.
- **Puzzle answers print the same day, upside-down at the footer.** Put the
  solution in `SlotResult.answer`; the entry point and `.answers` in the base
  template do the rest. Never carry an answer over to tomorrow.
- **Fixed-pitch content uses `var(--font-mono)`**, which is embedded on every
  page whatever the persona face is. And centre such a block by centring its
  box — `text-align:center` on `white-space:pre` centres each line separately
  and shatters any asymmetric ASCII art.
- **Update `docs/SLOT-STATUS.md` in the same commit as a slot.** A deviation
  from `SLOTS.md` is fine when it is reasoned, and is only fine if it is written
  down there.
- **Every collector ships a fixture** so the receipt renders offline and
  deterministically. Tests must not need the network.
- **Iterate with `--preview`, not paper.** Real prints are for end-of-phase
  verification only — screen previews lie about contrast, but paper is slow and
  finite.
- **Config over constants.** Tier weights, recency `tau`, budget, paths and keys
  live in `config.toml` / `.env`, never inline.
- **Nothing personal in the repo.** Names, places, dates, keys and taste go in
  `.env`, `config.local.toml` or the gitignored `data/` files, each with a
  committed example. The reader's name reaches a persona as `{name}` in
  `personas.toml` and a theme as `var(--reader)` - never written in.
- **`paper_mm` is a worst case, not an average.** The engine fits the draw
  before anything is fetched, so it only ever sees the spec. An optimistic
  figure gets a slot drawn onto a day it does not fit and the page overflows.
  `tools/papercheck.py` measures every slot against its claim; run it after
  changing any layout. The budget also reserves `paper.spine_reserve_mm` for
  the spine, which is never drawn and so can never be skipped.
- Match the surrounding code. Reference implementations for the three slot shapes
  (API, generated, image) are the pattern to copy.

## Working style for this project

- Build in batches. Once the contract exists, write 6–10 slots in a session
  rather than one at a time — consistency comes from doing them together.
- Subagents are for isolated API spikes ("work out Mapillary and return a working
  fetch"), not for slot implementation. Cold-start agents produce dialects.
- Update `ROADMAP.md` state in the same commit as the work.

## Commands

Run everything from the virtualenv: `.venv\Scripts\python.exe` (Python 3.11,
64-bit - the pins in `requirements.txt` do not install on anything newer).

```bash
python main.py --preview            # render today to PNG, no printing
python main.py --preview --offline  # fixtures only, no network, no API call
python main.py --date 2026-12-21    # force a date (a simulation, never recorded)
python main.py --dry-run            # full pipeline, no paper
python main.py --contact-sheet 30   # 30 simulated days side by side; offline, never recorded
python main.py                      # print
python tools/printpng.py out/x.png  # print a saved preview exactly as seen
python tools/printed.py 7           # what the last 7 real mornings actually said
python tools/slotcheck.py           # coverage + offline fixture smoke test
python tools/personacheck.py        # every persona's wiring
```

`--preview` of today records the morning unless one is already on file; use
`--date` for anything that is not today's real receipt.
