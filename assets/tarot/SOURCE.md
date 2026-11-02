# Tarot deck — provenance

Used by slot 132 (`slots/tarot.py`). See `docs/SLOTS.md` §132 for why this deck
and not another.

## The artwork

**Rider–Waite–Smith tarot, 1909.** Illustrated by **Pamela Colman Smith**,
designed with Arthur Edward Waite, first published by William Rider & Son,
London, in 1909.

## The scans

Downloaded from **Wikimedia Commons** by `tools/gettarot.py`, from the file
series `File:RWS1909 - NN Name.jpeg`. Commons describes them as scanned by
Saskia Jansen from an original 1909 "Roses & Lilies" deck in her personal
collection.

Credit line recorded on Commons:
<https://blog.goo.ne.jp/valet_de_coupe/e/10b39ab41d023e6b44bb7d7b7209c772>

## Licence

**Public domain.** All 22 major arcana files were checked against the Commons
API (`extmetadata`) on 2026-09-03 and every one returns
`LicenseShortName: Public domain` / `License: pd`. There is no Creative Commons
condition on any of them, so no attribution or share-alike obligation attaches.

Two independent reasons the artwork itself is out of copyright:

- Published 1909, so public domain in the United States (pre-1929).
- Pamela Colman Smith died in 1951, so life + 70 expired on 1 January 2022 in
  the UK and EU.

A faithful photographic reproduction of a flat, public-domain work generally
attracts no new copyright of its own, which is why the scans carry the same
status as the paintings.

Scans of a *different* deck tested along the way (Nicolas Conver, 1760) are
uploaded under CC BY-SA 4.0 and would need attribution if ever bundled. That deck
was rejected and is not here.

## Files

- `source/*.jpg` — the colour scans as fetched, ~6.2MB. The archive.
- `*.png` — final 1-bit cards baked by `tools/baketarot.py`, ~308KB. What the
  slot actually reads. Re-bake after changing `CARD_W` or the contour defaults.
