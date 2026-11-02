# SYSTEM.md — Overarching mechanics

How the machine works. `SLOTS.md` is the content catalogue; this file covers
everything that is not a single slot — personas, rarity, series, the input
channel, failure handling, and the self-referential machinery.

---

## 1. Hard constraints

- Epson TM-T20II, 80mm roll: 72mm printable, 203dpi, 8 dots/mm → **576 dots wide**
- **The width must be a multiple of 8.** Rows pack into whole bytes, so the
  raster stride is `ceil(width/8)`, taken from the image and never from the
  nominal width. A mismatch prints as diagonal smear rather than erroring.
- Paper budget **1030mm/day (8240px)**, `[paper] budget_mm`, of which 480mm is
  reserved for the spine (`spine_reserve_mm`). It is neither an economy limit
  nor a design one: **length is not a design constraint on this machine**. The
  roll is 80m and costs pennies, and nothing should ever be trimmed, dropped or
  shrunk to save paper. The ceiling is a guard against a runaway render — a
  slot in a loop, an image that failed to scale — and when a spine grows, the
  budget is raised so the rotating slots keep their 550mm. Legendary formats
  exceed even this and render with `strict_budget=False`.
- One text line ≈ 3mm. A full-width 576px square image = 72mm.
- **The printer has a cutter** (`GS V 66 n`, partial cut). See §1.4.
- Connection: **USB, straight to the `usbprint.sys` device interface.** No print
  queue, no driver install, no elevation, no Zadig — see §1.1.
- Rendering: **HTML/CSS at 576px → headless browser → 1-bit → ESC/POS raster**
- Schedule: **one morning run.** No daemon, no watcher, no event listeners.

### 1.1 Measured on the hardware

Verified by printing `tools/testpattern.py` and `tools/rendertest.py`. These are
measurements, not spec-sheet claims — trust them over the datasheet.

**Geometry transfers between printers; ink does not.** Any 203dpi head at 8
dots/mm shares everything expressed in *physical* terms: the type floor, the type
scale, hairline behaviour and the tarot card size are all functions of dot pitch.
What is *not* transferable is anything about **ink**: threshold, solid-fill
density and reversed-out legibility are properties of a specific printhead. A
better head lays more ink for the same instruction and so wants a *lower*
threshold. Re-measure them on any other printer; assume nothing carries over.

**Measure type through the browser, not through PIL.** Glyphs rasterised
directly by Pillow read about one pixel smaller than the same glyphs rendered in
Chromium and thresholded. Production is the browser pipeline, so its number is
the one that binds — a floor measured from PIL output is optimistic by exactly
that margin.

| | Result |
|---|---|
| **Absolute type floor** | **12px.** Below that is unusable at 203dpi. This is the hardware limit, **not a body size** — body is 19px and the tiny tier is 15px (§1.2). Nothing prints below 12px in any theme. |
| Hairlines | 1px rules and 2px-gap verticals all render distinct. Fine rules and dense line patterns are safe. |
| Raster banding | 128-row bands leave no visible seam. |
| Solid fill | Dense and even on the TM-T20II. **Reversed-out text is cleanly legible at 170** in both regular and bold, so the reversed-out legendary format is viable. At 220 it starts filling in. |
| Dithered ramp | Smooth, with a genuinely black dark end. |
| **Page threshold** | **170** on the TM-T20II. An antialiased hairline serif lands as mid-grey; below the cut it becomes pure white and the stroke vanishes, breaking glyphs in faces like Libre Baskerville. Too high and reversed-out text is eaten instead. Ink behaviour does not transfer between printers; re-run `tools/thresholdtest.py` on any new one. |
| **Reversed-out text** | **Always bold.** Threshold and reversed text pull opposite ways: more ink rescues positive hairlines but eats white glyphs. Use `.inv`, which carries the weight with it. |
| Physical margin | ~4mm of unprintable paper each side of the 80mm roll. 576 dots is the head's native width; `tools/widthprobe.py` confirms wider rasters clip. |
| Narrower rolls | A 58mm roll on the same printer measures 420 dots wide, which is not a multiple of 8: use **416**. |

### 1.2 Type scale

The 12px floor above is what the hardware can *resolve*. The house scale sits
deliberately above it, for comfort rather than for the minimum:

| | Body | Small | Tiny |
|---|---|---|---|
| **Default** | **19px** | **17px** | **15px** |
| Special Elite, Libre Caslon Text, Space Grotesk, Inter | 20px | 18px | 16px |
| IBM Plex Sans, Archivo | 21px | 19px | 17px |
| Barlow, Zilla Slab | 22px | 20px | 18px |
| VT323, IM Fell English | 23px | 21px | 19px |
| Almendra | 24px | 22px | 20px |
| Archivo Narrow | 26px | 24px | 22px |

17px is *small* text and 15px is *tiny* — neither is a body size.

**Sizes are set by measured characters-per-line, not by a uniform offset.**
`tools/personafonts.py` measures every body face in Chromium at 576px. On an
18px scale Libre Baskerville at 18px and VT323 at 22px both measure ~65
characters, so 65 is the house measure, and each face narrower than that takes
the size that brings it back. VT323 is a pixel font whose glyphs are so narrow
it gives **90 characters per line at 16px**; Archivo Narrow, a condensed face,
gives 90 at 18px. (A *monospace* gives ~53 at 18px — JetBrains Mono measures
53.3 — and the wide monospaced faces stay on the default size.)

**Then everything goes up 1px**, which read better on paper: every tier of every
face, the default included. The table is therefore "back to the house measure,
plus one".

Sizes live in `render/fonts.py` (`sizes()`), not scattered through the themes, so
a persona cannot quietly undercut them.

Nothing prints below 12px, ever.

Raising a size is **not** the fix for thin strokes dropping out — the page
threshold is (§1.1). A size bump costs paper and barely moves ink coverage; the
threshold moves it directly and costs nothing. Reach for the threshold first.

### 1.3 Design to the full width

The paper's ~4mm of unprintable edge **is** the margin. Layouts therefore use the
full 576px and add no gutters of their own — a full-bleed rule, black bar or
image runs 0 to 576 and still reads as inset on paper.

Take the number from `printer.base.WIDTH_DOTS`; never hardcode it.

Resist the CSS instinct to pad the body. Padding here is spent twice: once by the
printhead and once by us, and the result looks cramped.

### 1.4 The cutter

The TM-T20II has one, and all six ESC/POS cut variants were confirmed working on
it (`tools/cuttest.py`). We use **`GS V 66 n`** — feed, then partial cut — and it
is **on by default**.

Two reasons for that variant specifically. The cutter sits ~14mm above the print
head, so an immediate cut lands in the middle of what was just printed; the feed
variants exist to avoid exactly that, and doing the feed and cut as one command
beats feeding separately and hoping the timing holds. And a *partial* cut leaves
a small tab, so the receipt stays attached instead of dropping on the floor.

Printers without a cutter ignore `GS V`, so leaving it on is safe.

**The cutter never fires at the coupon's tear line — decided, not pending.** It
fires once, at the end of the whole job, to free the receipt from the roll. The
tear line stays manual: you tear it to take the coupon, so everything below the
line leaves with it. Cutting there would hand you a detached coupon and post the
receipt separately, which is backwards.

**Only ESC/POS raster (`GS v 0`), paper feed and the cut are used.** Everything else —
upside-down text, mirroring, double-width, barcodes, QR codes — is pixels we
generate ourselves, so we never depend on a cheap printer implementing a command
set correctly. `printer/usbwin.py` enumerates the device path at run time, since
it embeds the serial number and disappears when the printer is unplugged.

### The rendering rule

**No greys. No opacity.** The page threshold is binary: anything lighter than
the cut becomes pure white and vanishes. Texture must come from an actual
pattern - a hatch fill, a checkerboard, a dither - never from a light fill or an
alpha value. Rain bars drawn at `opacity: 0.25` print nothing at all.

**Threshold text, dither photos, never in the same pass.** Images are dithered to
pure 1-bit (Atkinson) *before* being embedded in the HTML as data URIs. The final
page pass is a straight threshold, which leaves already-binary pixels untouched
and keeps type crisp. Dithering a composed page is what makes thermal output look
like mud.

**12px is the measured body floor** (§1.1), so favour chunky, well-hinted faces.
Pick from Google Fonts and ship it — legibility is judged on real paper, not
agonised over up front, and a font is a one-line change.

---

## 2. Receipt theater

The page is a receipt, and the framing is carried by three elements.

### 2.1 The itemization

Every slot that printed today appears as a line item, priced by rarity. The
footer totals it.

```
--------------------------------
TAROT CARD            COMMON  0.30
WIKI: MOST READ       COMMON  0.30
NONOGRAM              COMMON  0.30
CITY MAP TILE       UNCOMMON  1.20
--------------------------------
SUBTOTAL                      2.10
RARITY              **...
No. 0147   02 SEP 2026
[CODE39 barcode of the date]
```

Pricing: common 0.30, uncommon 1.20, rare 6.00, legendary 50.00.

### 2.2 The coupon goes last. Always.

Section order is: masthead, weather, news, rotating slots, itemization, totals,
legalese, serial + barcode, **then the coupon**.

The coupon carries a tear line, and everything below a tear line is destroyed
when the coupon is torn off. Mid-page, redeeming a free coffee would cost the
itemization, the rarity stars, the serial number and the barcode. Real receipts
put coupons below the total for exactly this reason.

Anything else tear-off (the origami square, a cut-out card) follows the same
rule: **detachable content is terminal**, or it takes the receipt with it.

### 2.3 Rarity stars

Printed on **every** receipt, directly under the subtotal. One star for an
all-common day, five when a legendary lands. It is the summary of the day's draw,
so it is never itself withheld.

### 2.4 Absurd legalese (slot 146)

Occasional mock-legal fine print in the day's persona, set in small caps near the
itemization so it reads as genuine terms-and-conditions furniture. The register
is Terry Pratchett: straight-faced bureaucratic language applied to impossible
subject matter, ideally with a footnote that undermines the clause above it.

```
THE MANAGEMENT ACCEPTS NO LIABILITY FOR
PROPHECIES FULFILLED IN SPIRIT BUT NOT
IN LETTER.* NO REFUNDS ON WEDNESDAYS.

* OR IN ANY OTHER TENSE SUBSEQUENTLY
  DISCOVERED.
```

---

## 3. Personas

A voice is drawn each morning and restyles the whole page. Because the page is
rendered rather than typed, **the persona changes the typeface and layout, not
just the wording**. The bar is higher than a restyle: each persona prints a
different *document* — a ledger, a case file, a diner ticket, a playbill —
recognisable across the room before a word is read.

Each entry in `personas/personas.toml`:

| Field | Purpose |
|---|---|
| `name` | internal id — what the receipts table and the narrator's digest record |
| `display` | what the narrator and the other personas call it — never printed as a masthead (§3.7) |
| `rarity` | common / uncommon / rare (§3.6) - how fast the persona wears out, and how often it is drawn |
| `audition` | written but not yet designed; never drawn (§3.5) |
| `voice` | tone notes fed to the narrator prompt |
| `design` | the brief its theme is built to |
| `theme` | its CSS stylesheet |
| `font` | body face, as `--font` |
| `fonts` | display and accent faces, as `--font-display` / `--font-accent` |
| `art_tags` | which ASCII-pack and image moods it prefers |
| `vocabulary` | how it renames slot headers |
| `masthead` | lines the narrator writes fresh for the top of the page, with fallbacks (§3.7) |
| `speakers` | for a persona whose sections are dialogue: turns written `NAME:` are set as transcript blocks a theme can lay out in columns |
| `blocks` | this persona's own shape for a section whose form it may bend — the legalese and the coupon (§3.8) |
| `wants_history` | hand this persona true figures about itself — appearances, paper spent, first day — appended to its voice (`main.with_history`) |
| `variants` | how many masthead drawings the theme rotates by date (`data-variant`) |
| `variant_briefs` | one line per variant appended to the voice for that day, when a variant changes what the persona talks about (the Commentary Box's sport) |
| `tear_glyph` | the line above the coupon, set in the body face |
| `retired` | excluded from the draw |

The pool is sixteen, all live: the Clerk, OPS, the Oracle, the First Mate, the
Detective, the Daily Roll and the Bootleg Tape (common); Accounts Receivable,
Dot's All-Nite Diner, the Stage Manager, the Commentary Box and the Monkey
Astronaut (uncommon); the Machine, the Time Traveller, the Mimic and the
Revolutionary (rare).

The reader's name is never written into a persona: `personas.toml` says `{name}`,
`{NAME}` or `{initial}` and the loader fills them in from `[reader]` (QG_NAME in
`.env`); a theme prints it as `var(--reader)` or `var(--reader-caps)`.

### 3.0 The weather is the persona's own

Every persona draws the weather its own way (`render/weather_layouts.py`), set
with `weather = "..."` in `personas.toml`: **chart**, **parts**, **threedays**,
**dial** or **counted**. The facts are identical in all five - the layout is
presentation and decides nothing - but the section that prints every morning is
the one a persona is known by, so the ops officer gets a curve, the oracle gets
a 24-hour dial and the diner gets four cards.

Absent or unknown, a persona gets the chart.

### 3.1 Persona bleed

The persona does not only write its own sections — it reaches into the others at
a controlled dosage.

- **Always:** section headers. The micro-dare is never printed as "micro-dare";
  the ops officer files it as `TODAY'S MISSION`, the oracle as `THE SPELL FOR
  TODAY`. The same applies to the coupon, the banger corner and the cheat
  sheet.
- **Sometimes (~30%):** one sentence of framing around a factual slot.
- **Never:** the facts themselves. Weather numbers, puzzle grids, quote text and
  search results render as-is.

**News (slot 10) is capped lower than everything else.** It gets header styling
and at most a light touch of voice — never a rewrite.

**Callbacks spread across the page, not onto the weather.** When a header, a
masthead line or the small print refers to something else on the receipt, it
reaches for a headline, the puzzle, the quote, the joke or the weekday first;
outside its own section the weather is mentioned at most once a receipt (house
rule 7 in `narrator.system_prompt`). Real mornings showed it winning almost
every callback (2026-10-28): it is the one section every page has, it carries
the most concrete figures, and 13 of the 30 example lines in the persona voices
are about rain. The examples show register, not subject, and the narrator is
told so; the block instructions that listed the weather first as a callback no
longer list it.

### 3.2 Continuity and drama

The narrator receives a digest of the **last ~14 receipts** — personas used,
slots drawn, feedback received — and may reference *any* recent persona, not only
yesterday's. Grudges, alliances, running complaints and score-settling are
encouraged. The goal is a feud nobody designed.

### 3.3 Direct address (slot 131)

The persona occasionally drops the format and speaks to the reader directly.
It may introduce itself, complain about another persona, comment on the machine,
or taunt the reader with content never received. Not tied to a persona's first
appearance — it can happen any time.

### 3.4 Retirement

A persona accumulating consistent negative feedback can be given a farewell
receipt and set `retired = true`. Manual, not automatic — feedback volume is too
low to trust to a threshold.

### 3.5 Auditions

A persona is written before it is designed. `audition = true` marks one with a
voice, vocabulary, faces and design brief but no finished stylesheet.
`main.load_personas()` leaves it out, so it is never drawn and never offered to
another persona as a rival to feud with.

**Its voice can still be heard.** `--persona <name>` reaches into the auditions
and renders the persona on `personas/themes/_audition.css` — a deliberately plain
page with a banner saying what it is — until its own theme file exists, after
which the real theme previews from its first line. The narrator runs as normal.
An audition run is a rehearsal: it is never recorded, so it cannot reach the
continuity digest, consume a legendary format or pin tomorrow's slot.

A persona passes its audition when its theme is built to its brief (the
checklist in ROADMAP.md), and the line is deleted. Its first receipt is its
debut.

### 3.6 Rarity and persona recency

`pick_persona()` draws the tier first, then who within it.

**Rarity is not how good a persona is, it is how fast it wears out.** A persona
with somewhere to go on an ordinary Tuesday is common; a persona that is the same
strong joke executed identically every time is not, however good the joke is.
That is the only test. It is why the Daily Roll and the Bootleg Tape are common -
a tabloid's whole nature is that it comes out constantly, and both absorb a dull
day - and why Accounts Receivable is not: a KPI deck three times a month is the
one you would start groaning at.

Per-day weights live in `[personas]` in `config.toml` and are **50 / 35 / 15**.
A tier's weight is shared among its members, so writing another rare persona
makes the existing rares scarcer rather than making rare mornings commoner: the
odds of *a* rare day are that number and stay that number however big the pool
gets. The current 7 / 5 / 4 split:

| Tier | Personas | Each |
|---|---|---|
| common | clerk, ops, oracle, first mate, detective, Daily Roll, Bootleg Tape | 7.1% - about every fortnight |
| uncommon | Accounts Receivable, diner, stage manager, commentary box, monkey | 7.0% - about every fortnight |
| rare | TM-T20II, time traveller, mimic, revolutionary | 3.8% - about every 24 days |

The commons and the uncommons come out level at these counts, which is a
consequence of the pool's shape rather than the intent: the tiers only separate
again as the uncommon bench fills up. Nothing needs fixing for that to happen -
every persona written from here lands in a tier and dilutes it.

**Recency damping.** The same curve as the slots (§4) and the same two dials,
per persona and slower to recover, in `[personas] suppression` / `tau_days`
(0.95 / 14 against the slots' 0.9 / 10). The reader sees one page a day, so the
same face twice in a week reads as a broken machine even when the draw was
honest; the damping puts a persona at 5% of its weight the morning after it
printed, a third of that weight a week later and two thirds at a fortnight. A
persona that has never printed is undamped, so a debut lands early rather than
queueing. `Store.personas_last_seen()` reads it off the receipts table, for the
same reason the slot version does: the paper is the record.

The tier is drawn before the recency scoring, deliberately. Scoring all sixteen
in one weighted list lets damping leak between tiers - commons print oftenest, so
at any moment more commons are freshly damped, and the weight that frees goes to
whoever is not, which pushed rare mornings from 15% to nearly 18% in simulation.
Drawing the tier first spends that weight inside the tier, where it belongs.

**The draw is not a pure function of the date.** It is seeded by it, but it
reads what the machine remembers printing, so re-running a past day can
hand back a different persona than it did at the time. That is correct: the
history it was drawn against has moved on.

- **An empty tier is skipped**, not handed its weight silently - an engine that
  picks a tier and finds nobody in it looks exactly like a broken one.
- **Undecided:** whether a rare persona counts toward the rarity stars (§2.3) or
  earns a line in the itemization.

### 3.7 The masthead never names the persona

The persona is recognised by its document, never introduced by its name. A
theme empties `.wordmark` (the template still fills it with `display`, so the
audition placeholder prints it) and heads the page with something from its own
world: the Detective's title card is the case number, the Oracle's is the date
in blackletter under tonight's moon, the First Mate's banner carries the ship's
name, the Clerk's page is headed by the standing title of the volume and its
folio number, and OPS's by the handling classification over the addressing
block. **Two exceptions, by decision:** Dot's All-Nite Diner prints DOT'S / ALL-NITE DINER and
The Daily Roll prints its own masthead, because in both cases the name is the
furniture — a sign over a door, a paper's nameplate — not a persona introducing
itself.

**A third exception, of a different kind:** the Mimic prints a name at the top,
and it is the wrong one. It is wearing somebody else's page (3.9), so it writes
that persona's name in its own hand, misspelled by one letter - the impostor is
the only thing on this machine that introduces itself, and cannot spell what it
is introducing.

**Some of that head is written fresh every morning.** A persona may declare
`[persona.masthead.<key>]` fields in `personas.toml` - each an instruction, a
`max_chars` and a fallback list - and the narrator's single call returns them in
a `masthead` object alongside the sections (the schema is built from the
declaration, like everything else in it). The Detective gets a noir case title
and tagline, the First Mate one line of the ship's log. They are fiction and are
told so: no real people, headlines or figures, no day or date. With no narrator,
or a field it missed, the day's fallback prints instead - hand-written lists,
index-aligned so a title keeps its own tagline, picked by date. Printed as
`.mh-<key>` inside the masthead, and styled only by the persona that declared
them.

A theme may also draw more than one masthead. `variants = N` in `personas.toml`
makes the template carry `data-variant` (the date's ordinal mod N), so the drawings
rotate - consecutive mornings never repeat one, and a reprint gets the same. The
Detective has three opening shots.

---
### 3.8 Blocks: the sections a persona may reshape

Two sections at the foot of the receipt are a *form* as much as they are
content: the absurd legalese (146) and the coupon (11). The slot still supplies
the facts and the joke, but the persona says what that form is *for it*. The
coupon goes further: it draws no form or subject of its own, so its block is
the whole of its shape, and the narrator writes
its fine print too (`fine_print`, SLOT-STATUS §11). `[persona.blocks] legalese = "..."` /
`coupon = "..."` is appended to that slot's own narrator instruction
(`main.BLOCK_SLOTS`, which also covers the weather and the news if a persona
ever wants them). So the Oracle's small print is a warning spoken to you and her
coupon is a charm on a cord; the First Mate's are the day's shanty and a piece
of a treasure map; the Commentary Box's small print is not small print at all but the
full-time wrap-up, two pundits saying what we learned. A `speakers` persona has
its weather verdict, its slots, its coupon, its legalese and its masthead set as
transcript turns alike.
Without a `blocks` entry the slot's own instruction stands, unchanged.

**Block tables.** A sentence of form says what a block is; it
cannot keep it from being the same every morning, lay it out as a form, or
roll a lucky day. A block may therefore be a table, `[persona.blocks.<key>]`
(the keys are listed at the head of `personas.toml`; `main.block_spec`):

- **`picks`** - Python draws one per *appearance*, and goes round the whole list
  before any comes up twice (`main.rotate`, counted from the receipts strictly
  before today, so a reprint draws the same). A persona prints once a fortnight,
  so a draw seeded by the date alone lands the same pick on consecutive
  appearances. The narrator is told the pick as fact; its `label` prints
  (.blk-label - the Detective's disposition stamp, the black-book contact, the
  ration); its other plain fields become data-* attributes the theme draws from
  (data-units squares, data-kind's footer, data-where, data-grade). This is the
  OPS-mission `classes` idea, one level down.
- **`layout`** - "lines" or "labelled": the body is split into .ln rows, and
  "labelled" splits "LABEL: text" so a form can be a form (the Revolutionary's
  papers, the Machine's changelog, the Diner's findings). With `labels`
  declared the split holds even when the fields come back as one paragraph.
- **`chance`** - a lucky morning (the Commentary Box's raffle ticket wins about
  one day in twenty): the narrator is told it as fact, the theme reads
  data-lucky.
- **`fine_prefix`** - words the theme prints in front of the small print,
  stripped if the narrator writes them as well, which it does, told or not. A
  list when it has more than one way of saying it ("Scrawled on the back:").
- **`fallback`**, and a pick's own `body`/`fine` - the persona's offline copy,
  applied when the narrator did not write the block (`main.block_fallbacks`),
  so an offline morning prints a form shaped like the form.
- **`drawing`** - a picture Python makes fresh for each
  appearance, registered by name in `main.DRAWINGS` and called with the
  block's table, the appearance count, the day and the store. It returns a
  pick like any other (label, brief, offline body and fine), plus `svg`, which
  prints as .blk-drawing. A drawing that raises drops the picture, never the
  block. personacheck rejects a name that is not registered, since an unknown
  one would print nothing and say nothing.

Every block also carries data-no, data-dd and data-mm, like the masthead, so a
theme can number a ticket's seat or a flight rule's revision from them. The
Mimic borrows the whole table of whoever it wears, its own form over the top,
and marks it `worn`, so a drawing that keeps count can tell it is being worn.

**The treasure hunt**, the First Mate's coupon and the one
`drawing` so far (`render/treasure_map.py`). Every First Mate morning prints
one 25mm square of a treasure map to cut out and keep, beside the ship's log
of how the crew came by it; nine pieces make a map. The maps are listed in the
block (`maps`: seed, name, three landmarks each), and each is drawn whole from
its seed - a 600-dot chart of one island, cut three by three - so the piece
printed in March meets its neighbour printed in June dot for dot. Pieces go out
furthest from the X first and the X's own piece last, and the last log is the
dig. What makes nine scraps one map is continuity: the coastline and its two
ripple lines, the river and the dotted trail run across the cuts, the border
round the outside is graduated so edge pieces find their places, and each
piece carries its map's numeral and its grid square (II · B3) in its corner.

The generator keeps the pieces whole: the X sits well inland and clear of the
cuts, landmarks and their labels land on one piece together (a label across a
cut leaves a stray half-word on its neighbour), every piece that would be only
water gets something from the sea, and nothing is drawn under a piece's tag.
`TreasureMap.faults()` names what would spoil a map, and
`python tools/treasuremaps.py` draws each one whole and cut, and prints its
faults. The six listed maps were chosen by eye from the candidates and are
clean. After them, `map_for` goes round again on new seeds (+1000 a lap) that
nobody has looked at, so it takes the first seed from there that draws clean
(about one in twenty does not). The Mimic dressed as the First Mate prints a
forgery, a piece of an island that does not exist, tagged "?". It fits nothing
and takes no real piece out of turn. Never crossed bones on a map: anything
crossed reads as the X, so the bones are a fish skeleton.

**Masthead fields go round too.** A masthead field's `classes`
are drawn the same way as a block's picks - once per appearance, every one
before a repeat - rather than seeded by the date, and a field may carry a
`chance`: the share of mornings it prints at all. On the others it is not
asked for and not printed, and the theme can tell (`:has()`): the Monkey's
Ground replies on about a third of mornings, and on the rest the file reads
NO REPLY FROM GROUND. The Oracle draws two classes at once - the source of the
omen and the kind of counsel - so the two do not move in lockstep.

**A share price.** `[persona.stock]` prints a small panel over
the serial (`main.with_stock`, `main.stock_panel`): the close is the receipt's
own subtotal, the move is against the last receipt's, and the line is the
mornings before it - all read from the receipts table, so every figure is
real. Accounts Receivable runs it every morning as the reader's own ticker
(`{NAME}.L`), and its small print is the analysts' consensus on it.

**A real photograph.** `[persona.picture]` runs Wikimedia
Commons' picture of the day in the masthead (`main.with_picture`, from the
featured feed `sources/wikipedia.py` already reads), dithered at its final size
before it reaches the page, with the photo credit the licence asks for. The
masthead field it names is handed what the photograph really shows and
captions it: true about the picture, the persona's about everything else. No
picture, no caption field. Only the Daily Roll asks.

**Every persona declares its coupon:** the Clerk's is a warrant
drawn in legal hand, OPS issues an AUTHORISATION as signals traffic, the Oracle's
is a charm on a cord, the First Mate's a black spot, the Detective's a card
pressed into your palm, the Diner's a punch card, the Stage Manager's a ticket
stub, the Commentary Box draws its raffle on air, the Monkey's is a ration card
countersigned by Ground, the Daily Roll sells its back page, the printer issues
itself a token it cannot enforce, the Time Traveller's is redeemable for
something not invented yet, the Mimic offers a gift that is trying to be somebody
else's coupon and is catastrophically wrong, the Revolutionary's is a dead drop,
and the Bootleg Tape signs off with one for the road. `tools/personacheck.py`
ratifies this: it reads the persona file the way `main.py` does and reports the
blocks, the masthead fields and anything that would not reach paper.

### 3.8.0 Two things a masthead field may do

Both came from OPS's orders, and both are general.

**A field may draw its subject from a list.** `[persona.masthead.<key>] classes`
is a list of subject classes; `main.for_the_day()` picks one by date seed and
appends it to that field's instruction as the morning's class. The reason is
narrow and real: OPS's MISSION is a wide brief with one obvious good answer, and
a wide brief with an obvious answer prints that answer every day — the mission
came back as a version of "clear the oldest item" however the instruction was
written. Python decides *what kind of thing* today's is (a deferred clean, a
reconnection, an acquisition, a culinary first); the narrator writes what it
actually is. Facts and choices in Python, voice in the model: the house split.

**A field may name its own heading.** With `[persona] masthead_label_lines`, a
line written as `HEADING: text` is split by `main.masthead_html()` into
`.mh-label` and `.mh-text` spans for the theme to set as a chip and a line. The
pattern is deliberately strict — capitals, at most 15 characters, a colon and a
space — so an ordinary sentence containing a colon is never mistaken for one,
and a line that does not match simply prints as itself. Three of OPS's five
orders paragraphs use it: their headings are supposed to *follow from the
mission* (EQUIPMENT on a cleaning day, COVER on a social one), which a heading
fixed in a stylesheet cannot do.

### 3.8.1 Absorption: a masthead that swallows a slot

A persona's own furniture can grow into a slot's job. OPS files the day's orders at the top of the page — situation, mission,
execution, sustainment, comms — and the micro-dare (51) is *also* a one-line
instruction for the day, which OPS then prints further down under the heading
TODAY'S MISSION. Two missions on one sheet is one too many, and it is neither
the slot's fault nor the masthead's.

`[persona.absorbs]` maps a slot id to the masthead field that eats it:

```toml
[persona.absorbs]
51 = "mission"
```

On a day that slot is drawn, `main.absorb()` marks it absorbed and:

- **its section is not printed** — `build_html` renders every rotating slot
  except the absorbed ones;
- **the narrator is not asked to write one** — a body nobody prints is tokens
  spent on nothing;
- **the field is written from the slot's own text.** The drawn task is appended
  to that masthead field's instruction, so the mission *is* the dare, issued
  rather than suggested. It is not a fresh invention sitting next to a dare the
  reader cannot see;
- **the field may change shape for the day.** A masthead field can carry an
  `absorbed` table of its own — a longer instruction, a bigger `max_chars`, its
  own fallback list — merged over the ordinary one;
- **the theme is told.** `data-absorbed` on `.masthead` names the field, and the
  theme sets it at the scale of the section it replaced. OPS boxes the mission,
  folds its paragraph number into the label bar and steps the type up five.

**The line stays in the itemization and in the recorded draw.** It was drawn and
it is on the paper — it has only moved up the page. A receipt that dropped the
line would be lying about what it printed, and the archaeology and the
continuity digest both read that record.

### 3.9 Mimicry: a persona that wears another one

The Mimic has no page of its own. `main.mimicry()` picks whoever printed most
recently - the digest's choice, not a draw, because it has been reading the
receipts - and hands over that persona's **stylesheet, body face, display face,
variant count, speakers, section names and masthead fields**. `mimic.css` is
then appended after the borrowed theme (`theme_overlay`, the only use of it) and
is the only thing on the page that is the Mimic's own.

What it does not borrow is one face: its `own` face (Kablammo), for the one
line a morning where the disguise drops. Every other face is borrowed, the
accent included - keeping more of its own reads as a second persona shouting
over the first rather than a disguise slipping. The voices are **stacked rather than swapped**: the impersonated
persona's voice first, so the narrator has a character to do, then the Mimic's
over the top, so what gets written is that character done badly by something with
a second mouth. Its `[persona.blocks]` instructions are appended with what the
worn persona would really have written there, so the narrator can see the right
answer and get it wrong on purpose. It does not borrow `[persona.cipher]`, which
is why the Revolutionary's transmission prints in clear under a panel that still
says ENCIPHERED.

Seven mistakes, and only seven: the misspelled name, one line in its own voice at
the foot of the masthead, one heading upside down, one rule stood on its end, one
whole section moved to the wrong place, the anatomical diagram, and a second
barcode that really scans and says HELLO. Which lands where is keyed to
`data-moon` and `data-dd`. **One mistake per area, never two** - a page of solid
mistakes is a different persona, and this one has to be found rather than
announced.

`data-wears` carries the worn persona's name onto the masthead, which is how the
overlay repairs the two places where a mistake would collide with a borrowed
theme rather than sit on top of it. With nobody to copy - an empty digest -
`wears_today()` returns `None`, the Mimic keeps its own faces and the bare base
template, and the act goes worse, which is correct. `--wears NAME` forces a
victim.

### 3.10 The cipher is a real one

`[persona.cipher]` names a masthead field to encipher. The narrator writes the
message in clear; `cipher.py` enciphers it, adds the key and the sender's
explanation of it as two further lines the theme can set, and hands the plaintext
back for the **upside-down answers footer** - the house rule every puzzle on this
machine obeys (SLOTS.md, PUZZLES), and the reason the cipher can be a real one
rather than a decorative squiggle. A reader who cannot be bothered has the answer
on the same page, the wrong way up; a reader who can break it with a biro gets to.

Only the Revolutionary asks. Three ciphers, rotated by the theme's variant so
consecutive mornings are not the same puzzle, and all deliberately easy: a
**Caesar shift** with the words left whole, a **numbers station** where A is
simply one, and a **three-rail fence** printed as the fence, so the shape on the
paper is the method. The shift is the date's ordinal (1-25, never 0), so a
re-run of a past morning enciphers identically and two consecutive mornings never
share a key. The key prints on the same page, dressed as the broadcast's
frequency, and she then takes the credit for it in a line that gives the game
away - which is the persona. No pigpen: it needs a drawn SVG per message, and a
woman with one typewriter in a basement sends letters and figures.

    python cipher.py "MEET AT THE USUAL PLACE"   # all three, today


## 4. Rarity engine (slot 117)

**Draw 3–5 rotating slots per day** (average 4), fitted
to the remaining paper budget. A 60mm slot and a 12mm slot can share a day; two 60mm ones cannot. Some
of those draws will naturally be small filler-sized slots.

### Tier weights — per draw

| Tier | Weight | Price |
|---|---|---|
| common | **50%** | 0.30 |
| uncommon | **37%** | 1.20 |
| rare | **13%** | 6.00 |

Legendary is **not** part of this mix. It is a separate per-receipt roll at
**1 in 25** — roughly fifteen a year.

Uncommon is uncommon because its pool is large, not because the tier is scarce - with dozens of uncommons, any single one still
comes round rarely even when the tier is drawn often.

### What that actually feels like

A morning draws **3 to 5** rotating slots, uniformly — 4 on average, and a
pinned series part rides on top of that rather than taking one of them. It was
3 to 6 until a week of real mornings said six was too long (2026-10-28).
Measured over 400 simulated mornings:

| | |
|---|---|
| Slots a day | **4.1** |
| At least one uncommon or better | **~94%** |
| At least one rare | **~42%** |
| All-common day (1 star) | **~7%** |
| Legendary | ~15 a year |

**The draw count and the weights are coupled.** More draws is more chances at a
rare, so raising the count makes a rare morning commoner without the weights
moving at all: at 2–4 draws a rare lands on ~34% of mornings, at 3–5 on ~42%, at 3–6
on ~44%. Dropping the ceiling to 5 cost two points of rare days, so the
weights were left alone. If the count changes, recompute
rather than eyeball (`tools/mixcheck.py`).

### Other rules

- Per-slot weights live in `config.toml`, modulated by recency (§4.3).
- **Print the miss.** Occasionally show the failed legendary roll
  (`LEGENDARY ROLL: 1/25 — NO`). Near-misses are what make a hit land.
- **Legendary rolls use random.org**, so the receipt can honestly state the roll
  was decided by atmospheric noise. Falls back to the local PRNG silently when
  unreachable.
- **Legendary formats draw without repeats** until the pool is exhausted, so
  every legendary is one that has not been seen before. At fifteen a year the
  full set of 22 would take about eighteen months.
- **One-day-only slots** (solstice, birthday, Feb 29) bypass the draw entirely.

### 4.1 Legendary formats

The formats are pre-built because they are printer and renderer behaviours a text
model cannot improvise. The content inside them is written fresh on the day.

1. **Prints twice** — identical duplicate, the second stamped `CUSTOMER COPY`
2. **Breaks character** — all personas drop, plain monospace, direct address,
   never mentioned again afterwards
3. **Misprint from elsewhere** — a complete receipt dated six months out, or from
   another dimension, with invented data, stamped `MISPRINT — DISREGARD`
4. **Never-expiring coupon** — every other coupon dies at midnight; this one does
   not
5. **Blank but for one line**, dead centre
6. **Fully reversed out** — solid black page, white text
7. **Sign here** — a signature line and nothing else
8. **Full persona takeover** (slot 134) — the spine is abandoned
9. **Full short story** (slot 144)
10. **Milestone serials** — #500, #1000. Earned rather than rolled.
11. **Printed entirely upside-down** — native ESC/POS mode. No acknowledgement
    that anything is unusual.
12. **Corrupted print** — deliberate bit-rot: dropped scanlines, smeared blocks,
    a column of garbage halfway down. The machine appears to be dying. It is
    fine the next day and never mentions it.
13. **The torn receipt** — content stops mid-sentence against a ragged printed
    edge, as though the roll ran out. It does not resume tomorrow.
14. **One enormous QR** — a single full-width code filling the page, which decodes to
    the day's actual content. Deliberately hostile.
15. **Double-width** — the whole receipt in double-height, double-width text.
    Half the density, twice the length. The machine is shouting.
16. **A bill for what you did not get** — the itemization only, listing the slots
    that were *not* drawn today, priced, subtotalled. No content at all.
17. **Numbered edition** — `3 OF 50. THIS DESIGN WILL NOT BE PRINTED AGAIN.` A
    one-off layout, genuinely retired afterwards.
18. **The stranger** — a persona that is not in the pool. Appears once, is never
    drawn again, and the regular personas afterwards refer to it as a rumour they
    are not sure they believe.
19. **Another language entirely** — the full receipt in French, Latin or Old
    English, unexplained and untranslated.
20. **Mostly footnotes** — one line of content, then most of a page of daggers,
    asterisks and marginalia qualifying it. The legalese register taken to its
    logical end.
21. **Addressed to someone else** — a complete, plausible receipt made out to a
    name that is not the reader's, delivered anyway.
22. **A hole in the page** — content flowing around a blank cut-out shape,
    clearly meant to be removed. What it is for is never stated.

### 4.2 Short story weighting

The legendary story pool is weighted, not uniform:

| Band | Words | Paper | Share of the story draw |
|---|---|---|---|
| standard | 1,500–2,500 | 60cm–1m | ~90% |
| the long one | up to ~6,000 | up to ~3.4m | ~10% |

The full story is one format in the pool, so it prints about once a year, and
the long one about one time in ten. The weighting is about making the long one
feel like an event, not about saving paper.

### 4.3 Recency weighting

Draws are **not** independent, and not a strict shuffle bag either. A slot that
has just appeared becomes much less likely for a while, then recovers smoothly.
It is never fully banned — a repeat inside a week should be possible, just
unlikely.

```
multiplier = 1 - 0.9 * exp(-days_since_last_seen / tau)      tau = 10 days
```

| Days since last seen | Weight multiplier |
|---|---|
| 0 | 0.10 |
| 5 | 0.45 |
| 10 | 0.67 |
| 20 | 0.88 |
| 30 | 0.96 |

Both `0.9` (suppression depth) and `tau` (recovery speed) live in `config.toml`.
This is what stops three tarot pulls landing in one week and then nothing for two
months, without making the rotation feel mechanical.

The same curve applies within every tier. Legendary formats are the one exception
— they draw without repeats until the pool is exhausted.

---

## 5. Series engine

- **One series is active at a time.** Pool: jigsaw (slot 60), growing city map
  (slot 62). They alternate.
- **Rare to start.** Once running it prints at **common cadence** until complete,
  then a **~3 week cooldown** before another can begin.
- Jigsaw size **3×3 minimum, 5×5 maximum**.
- Every tile is numbered and grid-referenced, so assembly needs no guessing.
- The two-day recipe (slot 63) is a mini-series and is exempt from the
  one-at-a-time rule.

This produces roughly five or six distinct series a year, each running two to
four weeks — seasons rather than a permanent fixture.

---

## 6. Input channel

Everything inbound arrives by **email**: a dedicated mailbox read over IMAP with
an app password. No hosting, no web endpoint, no OAuth. One collector reads one
inbox and routes on the subject line.

| Subject prefix | Feeds |
|---|---|
| `FEEDBACK` | prompted feedback replies |
| `LETTER` | letter to future self (slot 22) |
| `PHOTO` | photo assignment and dead drop submissions (slots 66, 73) |
| `FRIEND` | a line from a friend (slot 67) |
| `TONIGHT` | note from 11pm-you (slot 69) |
| `IDEA` | response to a new-slot suggestion (slot 141) |

Processed message ids are recorded so nothing is consumed twice.

### 6.1 The QR slots

Three slots carry QR codes. Each is **uncommon and drawn independently**, so each
purpose keeps its own cadence:

| Slot | Purpose |
|---|---|
| 12 | prompted feedback |
| 22 | letter to your future self |
| 66 | photo assignment (dead drop, slot 73, is a variant) |

Every QR encodes a pre-addressed `mailto:` link, so scanning opens the mail app
with the right subject already filled in.

### 6.2 Prompted feedback

Feedback is a **specific question about a recent receipt**, asked by the persona
and drawn from the archive — not a generic rating.

> *The oracle wishes to know whether Tuesday's nonogram was beneath you.*

### 6.3 What feedback is for

Three independent uncommon slots yield roughly four signals a month. That is far
too sparse to drive automatic re-weighting, so **weights are hand-tuned**,
informed by the log.

Every reply is instead fed to the narrator. Personas respond to the reader's answers,
argue with them, and hold grudges about them. Feedback earns its place as story
rather than as a tuning signal.

---

## 7. Failure as content

**No collector may raise into `main`.** Each returns a typed result or `None`,
and `None` is handled one of two ways:

- **Silent drop** for low-stakes slots. The budget is reallocated.
- **A persona failure report** (slot 136) for slots worth mourning: a sincere
  apology, obituary or incident note about the slot that could not make it in
  today.

**Goodreads has a bespoke failure mode.** When the scraper breaks — and it will —
the receipt prints an escalating, cataclysmic in-persona bulletin along the lines
of `AGENT COMPROMISED — GOODREADS CRACKING DOWN`. The outage becomes a plot
point rather than a gap.

Running with the network off must still produce a complete, shorter receipt.
Never a crash, never a blank page.

---

## 8. Self-referential machinery

### 8.0 What printed is kept

Every recorded morning keeps more than its receipts row: the words of each
section as printed - header, body, small print, masthead - in the store under
`receipt:text`, and the page PNG in `[paths] archive` (`main.remember`).
`tools/printed.py` reads both back. It is for the reader's feedback, not the
narrator: nothing reads it into a page. A slot that wants its own past words
keeps them itself through `after_narration` (the joke, the running bit).
The contact sheet records into a scratch store and archives no image.

### 8.1 Receipt archaeology (slot 113)

The narrator reads the archive and reports a real pattern:

- "The Victorian clerk has appeared four times more often than anyone else."
- "Every nonogram this month, you rated down."
- "You have not had a rare drop in nineteen days."

The same patterns feed the conspiracy slot (106), where a true observation is
connected to a deliberately unhinged conclusion.

### 8.2 Changelog (slot 137)

When a slot appears for the first time the receipt may announce it, mixed in with
straight-faced nonsense entries: `removed herobrine`, `nerfed mosquitos`,
`gained sentience`.

### 8.3 Monthly report (slot 139)

Once a month: most-seen slot, rarest drop, persona leaderboard, total paper, API
spend, best-rated morning, longest streak, and gaps ("you were away four days in
March").

### 8.4 Welcome back

If nothing printed for three or more days, the next receipt opens by
acknowledging the absence.

### 8.5 Weekday awareness

Tonal only. The persona may know it is Friday. There are no structural weekday
variants.

---

## 9. Truthfulness

The receipt invents things on purpose, so invention is **marked**.

- **The invented word (slot 103)** carries a consistent typographic mark — a
  dagger, or a small `(apocryphal)` — on its fabricated etymology.
- **The real etymology (slot 32)** carries no mark. The two must be
  distinguishable at a glance.
- **The conspiracy theory (slot 106)** is always framed as nonsense.
- Weather, sky data, search results, quotes and prices are never embellished into
  inaccuracy, whatever the persona is doing around them.

---

## 10. The narrator

One Claude API call per receipt. It receives the facts and returns the voice.

### 10.1 Model

**One model, every morning: `claude-sonnet-5`.**

A stronger model on rare days is not worth it. Web-search results land in the
prompt and are billed as input, so a search morning on a bigger model costs
several times as much - one such receipt cost **$0.59** - and the step up in
prose is not visible on paper at 576px. The same morning on Sonnet is about
$0.24, and an ordinary one about $0.05: roughly $18–25 a year, most of it
search days.

**Prompt caching does not apply here.** Caches expire within minutes to an hour,
and this job runs once every 24 hours, so every call starts cold. Do not build
architecture around a cache that will never be warm.

### 10.2 Search happens inside the call

The live-search slots do **not** need their own agent loop. Declare web search as
a server-side tool on the request and the API runs it on Anthropic's
infrastructure, returning results as content blocks in the same response. The
narrator stays a single call even on days that need to go and look something up.

Server-tool failures do not raise — an error comes back as a result block with an
error payload. Check for it and fall back per §7 rather than assuming success.

### 10.3 Output contract

The narrator returns **structured JSON matching a strict schema**, one field per
drawn slot plus the persona furniture (headers, coupon, legalese, continuity
line). A response that fails schema validation is discarded and the receipt falls
back to plain templated copy — a flat receipt is fine, a broken one is not.

### 10.4 What it receives

- the day's persona and its voice notes
- a digest of the last ~14 receipts, for continuity and drama (§3.2)
- any feedback replies since the last run (§6.3)
- the drawn slots, each with its spec fragment and collected data
- the current running bit and changelog state

History-dependent slots — persona continuity, receipt archaeology, the running
bit, the changelog, tomorrow-predicted — are **ineligible until 14 receipts
exist**. On a cold start the machine has no past to refer to and should not
pretend otherwise.

---

## 11. Data store

`data/cache.sqlite`:

| Table | Holds |
|---|---|
| `receipts` | one row per real morning: day, serial number, persona, slots drawn, rarity counts, paper mm, API cost |
| `kv` | namespaced key/value: slot memories and cursors, series state and pins, used mailbox ids, the legendary formats seen, and the last-known-good payload of every source |

Recency (slots and personas) is derived from `receipts` rather than kept as a
counter, so it cannot drift from what actually printed.

---

## 12. Rationale for the non-obvious choices

Recorded so they are not second-guessed later.

**Series start at rare, not uncommon.** Once running, a series occupies a
common-tier share of receipts. An uncommon start would mean one is active nearly
all the time, which is exactly what would stop it feeling special.

**No automatic weight tuning.** Roughly four feedback signals a month cannot
support it. Acting on that little data would be noise dressed as personalisation.

**Rarity stars on every receipt.** A rarity summary that is itself rare tells you
nothing on the days you most want to know.

**TMDB for film stills, not scraping.** Free API, properly licensed imagery. Sites
that scrape stills are running a risk posture, not a licence.

**Mapillary for street imagery.** Open and free. Google's Street View Static API
is metered and needs billing attached.

**`Wikipedia:Unusual_articles` rather than the random endpoint.** Truly random
Wikipedia is mostly geographic stubs; the unusual-articles list is hand-curated
and reliably strange.

**Email rather than a web endpoint.** It removes hosting, a server, and OAuth from
the project in exchange for an IMAP app password.

**Legendary formats are pre-built.** "Prints twice" and "fully reversed out" are
printer instructions, not text a model can improvise. Only the content inside
them is generated fresh.

---

## 13. Genuinely unresolved

These need real-world data rather than a decision.

- **Persona count.** Now sixteen, and the tiered draw (§3.6) is only half an
  answer to it: a common still prints about once a fortnight, which is thin for
  a feud the narrator's 14-receipt digest can see. Whether commons want a much
  larger share than 50, or whether the pool wants a standing cast of three or
  four, is not knowable before a month of real mornings. Tune then.
- **Per-slot weights within each tier.** The tier odds are set; the weights inside
  them are arbitrary until the pool actually exists.
- **Whether the draw gives a day enough to read.** Three to six slots is the
  range; whether that is the right range is a question about content, never
  about paper — the budget is no longer near the answer and the spine is not to
  be trimmed for it.

### Held in reserve: the feature/filler split

Not being built now, but worth remembering if the rotation ever feels flat.

The idea: pull the small slots out into an untiered **filler** pool, draw two
tiered *features* from the 20mm-and-up slots, then spend whatever budget is left
on filler that does not count toward the tier mix or the rarity stars. When it
was written, 31 of 79 catalogue slots were costed at 15mm or less. The measured
worst cases have since moved almost all of them up (`tools/papercheck.py`):
only one of the built rotating slots claims 15mm or less, so
filler would have to be defined some other way — by weight of reading, say,
rather than by paper.

It would fix a real imbalance — the catalogue holds 16 common, 37 uncommon and
28 rare slots, so "uncommon" is the bulk of it rather than a step up from
ordinary. Recency weighting (§4.3) papers over most of that, which is why this
can wait.
