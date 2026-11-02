# ASCII art pack — slot 26

Two sources, drawn from as one pack.

## Harvested — `harvested.json`

The bulk of the pack, from [asciiart.eu](https://www.asciiart.eu), fetched by

    python tools/harvestascii.py            # fetch what is not yet harvested
    python tools/harvestascii.py --status   # pieces per tag

Pieces are tagged by the site's own categories through **`sources.toml`**, which
maps each persona art tag to the sub-categories that suit it. To give a persona
more (or better) art, edit its line there and rerun — already-fetched pages are
skipped, and tags are recomputed across the whole pack every run.

The artist is kept, and the receipt prints a small credit bottom-right unless
the site lists them as unknown or they already signed the piece ("jgs" in the
corner). To drop a piece that is misfiled or prints badly, add its id to `skip`
in `sources.toml`.

## Hand-placed — `*.txt`

One piece per file, printed exactly as written, after header lines:

    # tags: ornament, engraving
    # artist: someone          (optional; prints the credit)

**Add a piece by dropping in a file.** No code change, no registration.

## Rules, for both

- **74 columns maximum.** A wide piece is set smaller rather than wrapped, down
  to the 12px type floor, and 74 columns of JetBrains Mono at 12px is 533px - the
  section body, which the template pads, is about 540. Narrower pieces print at
  up to the full small size.
- **26 rows maximum**, which is what the slot's `paper_mm` is costed at.
- **Tags decide who gets it.** Four days in five the piece shares a tag with the
  persona's `art_tags` in `personas.toml`; the fifth is anything at all. Pieces
  printed in the last 60 draws are skipped.
- Dense characters (`#`, `@`, `*`, `_`, `|`) survive the page threshold; a piece
  built mostly from `.` `'` `,` prints faint, and the harvester drops those.
