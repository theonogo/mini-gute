# ROADMAP.md — State, and what is left

`SYSTEM.md` is how the machine works. `SLOTS.md` is what it prints, and
`SLOT-STATUS.md` how each built slot does it. This file is where the project
stands and what is still open. Update it in the same commit as the work.

---

## Context

A thermal receipt printer prints a personal brief every morning. It is a for-fun
project that runs once a day, so the failure mode that matters is a blank or
half-printed receipt — never a stack trace. Every module degrades: if a source
dies, that slot is dropped or mourned in character, and the rest still prints.

Python owns the facts. Claude owns the voice. A rotating persona restyles the
page — typeface and layout, not just wording — and a rarity engine decides what
lands each day.

---

## Architecture

```
tools/morning.ps1 (a desktop shortcut, or a scheduled task)
  → main.py
      1. pick_persona(date)      tiered, recency-damped draw → voice + CSS theme
      2. selection.select(date)  3-5 draws, tier-weighted, recency-damped,
                                 budget-aware; separate 1/25 legendary roll
      3. safe_fetch(slot)        only for the drawn slots. Isolated, never raise
      4. narrator.write()        persona prose + per-slot copy (JSON out)
      5. build_html + Renderer   Jinja2 → HTML @576px → Playwright → threshold
      6. emit                    printer | PNG preview, then record the morning
```

The invariants are in `CLAUDE.md`. The short version: no collector raises into
`main`; threshold text, dither photos, never in the same pass; 576px wide, a
multiple of 8, from `printer.base.WIDTH_DOTS`; length is not a design
constraint; slot IDs are stable.

**Hardware.** Epson TM-T20II on an 80mm roll, 203dpi, 576 dots across, with a
cutter, driven straight through the Windows `usbprint.sys` device interface. The
numbers that depend on the printhead (page threshold 170, reversed-out weight)
were measured on paper and are recorded in `SYSTEM.md` §1.1; re-measure them on
any other printer with the tools listed there.

---

## Where it stands

| Phase | | State |
|---|---|---|
| 0 | Skeleton — config, store, `.env` for everything personal | done |
| 1 | Raster path to paper — ESC/POS raster, USB backend, PNG preview | done |
| 2 | Renderer — HTML to 1-bit, dithering, embedded fonts | done |
| 3 | Layout and personas — template, themes, `--contact-sheet` | done |
| 4 | The slot contract — `safe_fetch`, registry, coverage | done |
| 5 | Spine — weather, news, coupon, legalese | done |
| 6 | Narrator — one call, run-time schema, templated fallback, web search | done |
| 6.5 | Persisted receipts — serial numbers, history, continuity | done |
| 7 | Selection engine — tiers, recency, budget, legendary roll | done |
| 8 | Input channel — one IMAP mailbox, seven slots | done |
| 9 | Build-out — **84 of 94 slots**, 13 of 22 legendary formats | mostly done |
| 10 | Ship — a one-click launcher | done; real mornings pending |
| 11 | A designed document for every persona — all sixteen live | done |

**Printing by hand, on purpose.** There is no schedule: the "Morning receipt"
shortcut (made by `tools/shortcut.ps1`, on the Desktop and in the Start menu)
runs `tools/morning.ps1`, which uses the venv python from the repo root and
appends every run, timestamped, to `out/morning.log`. The window closes itself
after a good run and stays up after a bad one. Arguments pass through to
`main.py` (`tools\morning.ps1 --dry-run`). Running it twice in a day prints
twice. For a schedule instead: a daily task running the same command, with wake
timers allowed in the power plan.

---

## Open

### Before tuning anything
- [ ] **A month of real mornings.** Much of `SYSTEM.md` §13 - the persona count,
      per-slot weights, whether 3–5 draws is right (it was 3–6
      until a week of paper said too long) - is explicitly "tune after
      real mornings". `tools/mixcheck.py` and `--contact-sheet` give the
      simulated picture meanwhile.
- [ ] **Paper verification of the newest furniture.** Several personas' latest
      blocks (the second round of picks, the treasure map pieces) have been
      previewed narrated but not yet printed. Real prints are end-of-phase only.

### Slots not built
- [ ] **13 Lichess daily puzzle** - unbuildable as specified: the daily puzzle
      cannot be filtered by rating and the catalogue wants easy ones. Needs the
      downloadable puzzle database. Also needs the pieces drawn as SVG paths,
      since no embedded face carries the chess glyphs.
- [ ] **70 Headline from 100 years ago** - Chronicling America returns 403 on
      both its old and new Library of Congress endpoints. Not to be worked
      around by spoofing a browser.
- [ ] **123 Spotify Code** - the scannable endpoint returns a valid-looking code
      for a nonsense playlist id, so a wrong URI prints a code that scans and
      goes nowhere, with no way to detect it. Unsafe without API access.
- [ ] **60 Jigsaw** - on hold. The series engine supports it; the curated image
      pool does not exist.
- [ ] **45 Countdowns** - needs its dates, which belong in `.env` or the local
      config.
- [ ] **29 Film frame** (TMDB), **145 Street guess** (Mapillary) - not started.
- [ ] **58 Micro-print** - needs an explicit carve-out from the 12px type floor
      before it is built (`SLOT-STATUS.md`, open questions).

### Legendary formats not built
`legendary.BUILT` has 13 of the 22 in `SYSTEM.md` §4.1. Still to build, by
number: 3 misprint from elsewhere, 4 never-expiring coupon, 10 milestone serials,
15 double-width, 17 numbered edition, 18 the stranger, 19 another language
entirely, 21 addressed to someone else, 22 a hole in the page. 15 and 21 need
`main.py` to hand a format the receipt HTML before the first render.

### Ideas with no home yet
- [ ] **Persona top lines.** Go through the sixteen and decide which want a line
      or two of their own at the very top - an opening exchange, a greeting, a
      note before the first section - the way the Commentary Box's two men set
      the scene and the Stage Manager gives the running time. Not every persona
      needs one.
- [ ] **Message in a bottle** - a First Mate idea; persona free space (109) is
      the candidate home.

---

## Adding a persona

Write the entry in `personas/personas.toml` with `audition = true`: it is then
never drawn, never a rival and never recorded, and `--persona <name>` renders it
on `themes/_audition.css` until its own theme exists (`SYSTEM.md` 3.5). It
passes its audition when:

- [ ] its faces survive paper: `tools/personafonts.py <name> --print` read on the
      roll, noting which faces have no bold, since reversed-out text on those
      takes the 400 (sizes are measured into `render/fonts.py`)
- [ ] its theme is built to the brief within the rendering rules: 1-bit, no greys
      or opacity, texture from patterns, reversed-out via `.inv`, nothing under
      12px, full bleed, weights from `var(--bold)`
- [ ] `tools/personacheck.py <name>` reports no problems
- [ ] its spine is measured, and `paper.spine_reserve_mm` raised if it is the new
      tallest (`budget_mm` with it)
- [ ] it is rendered beside the others; if it does not look like a different
      document, it is not done
- [ ] it is printed on paper once
- [ ] the `audition` line is deleted

---

## Verification

- **`--preview` is the primary loop.** Exact full-width bitmap to PNG. Iterate
  layout, personas and slot mixes without burning paper.
- **`--contact-sheet 30`** — thirty simulated days at once, a week to a row, to
  eyeball persona rotation and whether the rarity mix actually feels right.
  Offline and never recorded, so it costs nothing to run. `tools/mixcheck.py`
  gives the numbers over longer runs, without the pictures.
- **`--date 2026-12-21`** — force a date for solstice deltas and one-day slots.
- **`tools/slotcheck.py`, `tools/personacheck.py`, `tools/papercheck.py`** —
  coverage and every fixture, every persona's wiring, every slot's paper claim.
- **`tools/printed.py`** — what real mornings actually said, section by
  section (`--slot 149` for one section across them all), with the page PNG
  kept in `out/archive`. Feedback on a morning is checked against this rather
  than a re-run, which draws the same slots and writes different prose. Kept
  from 2026-10-29.
- **Network off** must still produce a complete, shorter receipt.
- **A real print** at the end of every phase. Screen previews lie about contrast.
