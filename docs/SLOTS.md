# SLOTS.md — Content catalogue

Every approved slot. Mechanics — personas, rarity, series, the input channel,
failure handling — live in `SYSTEM.md`, which is worth reading first, since every
entry below assumes it.

IDs are **stable**. Never renumber them, and never reuse one from the CUT
table at the end.

### Paper arithmetic

Current figures, from `[paper]` in `config.toml`:

| | mm |
|---|---|
| Daily budget (`budget_mm`) | 1030 |
| Reserved for the spine (`spine_reserve_mm`) | 480 |
| **Left for rotating slots** | **550** |

The spine is never drawn, so it is reserved rather than fitted. It is the
persona's own document — masthead, weather layout, news, end blocks — and its
height varies by hundreds of millimetres between personas; the tallest measured
is the Mimic wearing the Daily Roll, ~456mm. That spread is why the selection
engine draws the persona *before* fitting slots to the budget (`SYSTEM.md` §4).

**3–5 slots are drawn per day**, 4 on average. Six read as too long on real
mornings (2026-10-28), so the ceiling came down by one.

**Length is not a constraint.** Paper is cheap and the roll is 80 metres; the
budget is a guard against a runaway render, never a ration (CLAUDE.md
invariant 3). If a page wants to be long, raise the budget.

The `paper_mm` in each entry below is the catalogue's original estimate. A
built slot's worst case lives in its spec and in
`[slots.paper_mm]`, measured by `tools/papercheck.py` — that figure, not this
one, is what the engine fits.

Tier weights and the resulting frequencies are in `SYSTEM.md` §4.

### Entry format

```
**<id> · <name>** — <tier> · <paper> · <data source>
<spec>
```

Tier is `spine`, `common`, `uncommon`, `rare`, `legendary`, `occasional`,
`variant of <id>`, or `n/a`. Every entry states one; there is no default.

---

## SPINE — prints every day

**1 · Header and receipt theater** — spine · 25mm · no deps
Persona-styled wordmark, date, incrementing receipt number, and a CODE39 barcode
of the date. The itemization block sits at the footer — see `SYSTEM.md` §2.

**2 · Weather verdict** — spine · 15mm · Open-Meteo (free, no key)
The call on what today actually requires. Range widely: jacket, umbrella,
sunglasses, "don't bother going outside before eleven". Never reduce it to a
binary jacket yes/no. The persona names and frames the section.

**3 · 24h temp and rain chart** — spine · 30mm · Open-Meteo
Rendered chart of the temperature curve with precipitation bands, so the timing
of rain is visible rather than just its likelihood. Real graphics, not ASCII.

**4 · Delta vs yesterday** — spine · 5mm · Open-Meteo + cache
"Three degrees colder than yesterday." Calibrates against lived memory instead of
an abstract number.

**5 · Sunrise, sunset and daylight delta** — spine · 10mm · Open-Meteo
Sunrise, sunset, total daylight, and the change since yesterday (−3m18s).

**10 · News ×3** — spine · 35mm · RSS + Claude
Three headlines ranked against `data/profile.md`, one line each. They do not have
to be serious — a genuinely strange story counts as news — but serious news
is not avoided either: an important story prints even when it is grim. Persona touch is capped
lower here than anywhere else: header styling and a light flavour only, never a
rewrite.

**11 · Coupon** — spine · 20mm · Claude
One absurd redeemable with a tear line. The format rotates every day across the
whole bureaucratic family: coupon, permit, warranty card, summons, procrastination
ticket, terms and conditions with a signature line, collectible ticket stub.
Variety is the point. The persona flavours it sometimes but not always — a plain
absurd coupon is as good as a themed one.

**146 · Absurd legalese** — occasional · 15mm · Claude
Small-caps mock-legal fine print near the itemization, in the day's persona. Terry
Pratchett register: bureaucratic language applied straight-faced to impossible
subject matter, with a footnote undermining the clause above it. Example in
`SYSTEM.md` §2.4.

---

## WEATHER AND SKY

**35 · ISS pass times** — rare · 12mm · Open Notify / N2YO
When it crosses tonight, and where to look.

**36 · Visible planets tonight** — rare · 20mm · skyfield or ephem, offline
What is up there and roughly where.

**37 · Moon phase** — common · 15mm · local calculation
Rendered small. Pure maths, no network, never fails.

**38 · Star chart** — rare · 70mm · skyfield + renderer
A real rendered chart of tonight's sky. Expensive in paper, so rare only.

**72 · Friend timezones** — uncommon · 20mm · config list
What time it is where friends are and who is currently awake. Each entry carries
that city's temperature too.

---

## PUZZLES

House rule: **answers print the same day, upside-down at the footer.** Nothing is
carried over to tomorrow.

**13 · Lichess daily puzzle** — uncommon · 55mm · Lichess API (free, no auth)
Rendered as a real board. Filter on puzzle rating and keep them **easy** — no
mate-in-five.

**14 · Nonogram** — common · 60mm · local generator
Date-seeded, 5×5 or 10×10.

**15 · Connections-style word grid** — common · 40mm · Claude
Sixteen words, group them into four. Circled with a pen.

**16 · Micro-maze** — uncommon · 50mm · local generator

**17 · Cryptic crossword clue** — uncommon · 10mm · Claude
The cheapest puzzle available, and good filler when the budget is tight.

---

## SERIES

One series runs at a time, alternating between the two below. Rare to start, then
common cadence until finished, then a cooldown. Scheduler in `SYSTEM.md` §5.

**60 · Jigsaw** — rare to start, common while running · 50mm · image slicer
One tile per print, assembled into a picture. **3×3 minimum, 5×5 maximum.** Tiles
are numbered and grid-referenced so assembly needs no guessing. The first card of
a series should feel like a find.

**Source pool is mixed**, so the *kind* of thing being assembled is itself a
surprise: public-domain paintings (reusing the museum APIs from slot 23), the
reader's own photos, a curated pack dropped into a folder, and general striking
images. Every
candidate passes a contrast pre-filter before a series starts — a low-contrast
source dithers to mud and wastes three weeks of mornings.

**62 · Growing city map** — rare to start, common while running · 50mm · map tiles
The same mechanic with map tiles, assembled across a wall.

**63 · Two-day recipe** — uncommon · 25mm · Claude + cache
Day one prints a shopping list. Day two prints the simple, genuinely good recipe
those ingredients make. Exempt from the one-series-at-a-time rule.

---

## INPUT LOOP

Three slots carry QR codes, each uncommon and drawn independently. Every QR
encodes a pre-addressed `mailto:`, so scanning opens the mail app ready to send.
Routing table in `SYSTEM.md` §6.

**12 · Prompted feedback QR** — uncommon · 30mm · qrcode + cache
The persona asks a specific question about a recent receipt, drawn from the
archive, rather than requesting a generic rating. Replies become narrative fuel:
personas respond to and argue with the answers. They do not auto-tune weights.

**22 · Letter to your future self QR** — uncommon · 30mm · IMAP + cache
Written whenever the mood strikes, printed back on a random morning months later.

**66 · Photo assignment QR** — uncommon · 30mm · Claude + photo folder
An assignment such as "photograph something red today". The reply lands in the
photo folder and resurfaces later as a printed photo, so the system feeds itself.

**73 · Dead drop** — variant of 66 · 15mm · local maths
Random coordinates within 2km. Go there and photograph it.

**67 · A line from a friend** — uncommon · 20mm · IMAP
Friends email the mailbox and their line prints. Kept deliberately simple — an
email address is the entire interface, with nothing to host.

**69 · Note from 11pm-you** — uncommon · 20mm · IMAP
The same mechanism, written at night and delivered at breakfast.

**141 · New slot suggestion** — rare · 20mm · Claude + QR
Claude proposes a slot it thinks should exist, with a QR to reply with a verdict.

---

## DISCOVERY AND CULTURE

**23 · Painting of the day** — uncommon · 60mm · Met, Rijksmuseum, Art Institute
of Chicago, Cleveland
Halftoned, with one line of context. Rotating four museum sources means it never
repeats and never runs dry.

**24 · Dev knowledge** — uncommon · 20mm · Claude + curated list
One genuinely useful thing: a CSS property, git flag, shell one-liner, browser
API, editor trick. **Range across all of those, not just CSS.** The bar is
something the reader could plausibly ship this week — interesting and useful, never
obscure, never code golf or trivia.

**25 · Book quote** — common · 25mm · Goodreads scrape
From his read list, kept in `data/books.txt`. Polite delays, every success cached to `quotes.json`, any
failure quietly serving a cached quote. When the scraper finally breaks it does so
loudly and in character — see the Goodreads failure mode in `SYSTEM.md` §7.

**26 · ASCII art** — common · 76mm · asciiart.eu harvest + Claude
A local pack harvested from asciiart.eu and tagged by its categories; Claude picks
the piece that fits the persona, with a random draw as fallback. A small credit
names the artist when known.

**29 · Film frame** — uncommon · 55mm · TMDB API
Name the film; answer upside-down. TMDB provides properly licensed stills and
backdrops on a free key. **Popular films and easy frames only.**

**30 · Wikipedia rabbit hole** — common · 15mm · Wikipedia API
One sentence plus a QR to the rest, framed as an assignment rather than a fact.
Draw from a local harvest of **`Wikipedia:Unusual_articles`**, a hand-curated list
of genuinely strange pages — the random endpoint mostly returns geographic stubs.

**31 · Untranslatable word** — uncommon · 12mm · Claude
A word from another language with no English equivalent.

**32 · Etymology of the day** — uncommon · 12mm · Claude
Where a familiar word actually came from. Sometimes runs as a word-of-the-day
instead. This is the **true** one and carries no apocryphal mark, so it must be
distinguishable at a glance from slot 103.

**33 · Logical fallacy or cognitive bias** — uncommon · 15mm · Claude
One bias, plus how it will specifically get him today.

**34 · What's in season** — uncommon · 15mm · seasonal data + Claude

**70 · Headline from 100 years ago** — uncommon · 20mm · newspaper archive
A real headline from exactly this date, a century back.

**84 · Wallet cheat sheet** — uncommon · 45mm · Claude + config
Cut out and keep. Rotate widely across topics: keyboard shortcuts, knots, unit
conversions, the phonetic alphabet, chord shapes, regex.

**85 · A line of sheet music** — rare · 35mm · ABC notation via abcjs
Real notation rendered in the page, not tab. The persona chooses the song.

**125 · XKCD of the day** — uncommon · 60mm · XKCD JSON API

**132 · Tarot card** — common · 72mm · Rider–Waite–Smith 1909 + Claude
A card image with the persona's own reading printed underneath.

**Deck: Rider–Waite–Smith, 1909.** Five decks were scored on real scans. The
woodcut decks (Conver 1760, Dodal 1701) were **rejected**: their flat colour
fills have no underlying outline to recover and became black masses no threshold
could rescue. RWS is coloured too, but Pamela Colman Smith drew heavy black
outlines beneath the colour, and `render.prepare_contour` recovers them as clean
line art.

**The deck is baked, not processed live.** `tools/baketarot.py` writes final
1-bit cards to `assets/tarot/<slug>.png` (264KB total, versus a 6.2MB colour
archive). The slot prefers those — the contour pass costs ~87ms a card and there
is no reason to repeat it at 07:00 every morning. Re-bake after changing `CARD_W`
or the contour defaults.

*Size is the binding limit, not deck style.* 132px (16mm) is unusable: the robes
blob into one black mass. **256px (32mm)** is the floor — face, beard, eagle
shield and cartouche all read. **320px (40mm)** resolves individual feathers and
chain links, and is the size used — exactly on the detail threshold, as small as
the deck goes without losing the line work. Card height is ~1.72× width, so
320px costs ~69mm before the reading text.

*The image threshold is NOT the page threshold.* The page threshold rescues
antialiased type (`SYSTEM.md` §1.1). Line art wants far less ink. Two different
knobs solving two different problems; do not unify them.

*No fixed threshold works across a deck.* How much dark ink each card carries
varies enormously, so the contour weight is binary-searched per card to hit a
target ink coverage: what we actually want is constant *apparent density*, not a
constant grey value.

*Licensing.* All 22 RWS scans were checked against the Commons `extmetadata`
API: every one returns **Public domain**, with no Creative Commons condition, so
nothing is owed. Provenance is recorded in `assets/tarot/SOURCE.md`.

If the art is missing the slot degrades to a drawn card frame, so it always
prints — see `slots/tarot.py`.

**133 · Check out this place** — rare · 40mm · web search
A small advertisement for a new or newly well-reviewed place nearby.

**138 · Wikipedia most-read yesterday** — common · 15mm · Wikipedia API
The article people actually read, which is reliably stranger than the news.

**143 · Wise saying** — common · 12mm · Claude
Marcus Aurelius, Sun Tzu, that register.

**130 · Fun fact** — common · 15mm · Claude + web search
Sometimes a straight fact, sometimes filtered through the persona.

**145 · Street guess** — rare · 50mm · Mapillary
A street-level photo from the neighbourhood; guess where it is. Mapillary is open
and free; Street View is metered and needs billing.

**123 · Spotify Code** — uncommon · 20mm · no auth
A persona-curated playlist, printed as **Spotify's own scannable Code** rather
than a QR. The `scannables.scdn.co` image endpoint needs no authentication. It is
undocumented and may change without notice; when it breaks it gets the persona
failure-report treatment.

**149 · Joke** — common · 20mm · Claude
A joke the day's persona would actually tell — not a joke with a persona voice
bolted on. The clerk's joke and the duty officer's joke should be different
jokes, not the same joke twice.
The **form** rotates so it does not become one shape every day: one-liner, pun,
question-and-answer, observational, definition, misdirection, rule of three,
escalation. The day picks a form and an everyday subject; the persona writes
into them. It has to be funny to anyone first — the persona is the delivery.

**150 · Horoscope** — common · 20mm · Claude
A reading for a star sign that **does not exist**. The persona invents the sign
and the reading together, so the sign is as much in voice as the prediction is.
About one day in eight it uses a real zodiac sign instead, which is what keeps
the invented ones funny.

**151 · The persona's printed object** — common · 110mm · Claude
The day's persona designs and writes one small printed thing from scratch, in
its own voice and visual style: a dog tag, a playbill, a cheque for nothing, a
treasure map to the kraken. What it is comes from that persona's own list in
`assets/objects.toml`; how it looks is the model's. Mostly absurd. Replaces the
cut origami (90).
The invention is stated rather than marked with a symbol (`CLAUDE.md` invariant
8): "sign invented on the premises" is both the disclosure and the joke, and a
dagger here would be humourless. On a real-sign day it says that instead.

**147 · Poem of the day** — common · 12mm · public domain corpus
A **complete** short poem every time — Dickinson, Bashō, Hopkins. Finished in one
morning, no commitment, no serial to keep up with.

**148 · Three-part short story** — rare · 40mm · public domain corpus
A short story split across three consecutive mornings. Long enough to be a real
read, short enough to actually finish.

---

## LIVE SEARCH

The flakiest slots on the receipt — slowest, likeliest to return nothing. All are
uncommon or rarer, and all have cached fallbacks.

**93 · Banger corner** — uncommon · 15mm
One thing that genuinely got better yesterday. The persona renames the section
each time, but the spirit of the name stays.

**94 · GitHub repo that blew up** — rare · 18mm
With an honest line on whether it is any good or merely hype.

**95 · What's on in the city tonight** — uncommon · 18mm
One event, filtered to taste. Venue listings are unstructured HTML no API covers.

**96 · Someone solved something** — rare · 18mm
A result from the past week, in three lines.

**98 · Today's best sentence** — rare · 15mm
The single best-written sentence found today, attributed. Curatorial rather than
informational.

**99 · Curio price check** — uncommon · 10mm
An object, auction lot or oddity chosen to suit the persona or the reader's taste —
noteworthy or strange, never mundane — with its price. The number only, never
advice.

---

## SEARCH AND JUDGEMENT

**110 · Explain this like I'll be asked at lunch** — common · 25mm
The day's most-discussed thing in three lines, enough to hold a conversation.

**111 · Steelman** — rare · 30mm
Something he would likely disagree with, inferred from `profile.md`, argued well
in four lines.

**112 · Connect two headlines** — uncommon · 20mm
A non-obvious link between two of today's stories.

**113 · Receipt archaeology** — rare · 20mm · cache only
Patterns in the receipts themselves: persona frequencies, rating streaks, drought
lengths. Also supplies real patterns to the conspiracy slot.

**114 · A person worth knowing about** — uncommon · 25mm
Someone remarkable and largely unknown.

**115 · Three outlets, one story** — uncommon · 25mm
The same story in three framings, one line each.

**116 · You were wrong about** — rare · 20mm
Revisit an old prediction or story and score how it actually turned out.

---

## GENERATION AND PERSONA

**101 · Persona continuity** — uncommon · 10mm · Claude + cache
Today's persona comments on the others. Not only yesterday's — anyone from the
recent archive is fair game, and drama between them is encouraged. See
`SYSTEM.md` §3.2.

**102 · A running bit** — rare · 10mm · Claude + cache
A joke invented once and called back at unpredictable intervals forever.

**103 · A newly invented word** — rare · 15mm · Claude
A word the reader needs that does not exist, with an invented etymology. **Must carry a
consistent mark identifying it as false**, so it is never confused with slot 32.

**104 · Tomorrow's receipt, predicted** — rare · 25mm · Claude + cache
Guesses tomorrow, then grades its own accuracy the following day. Written in
persona, with the in-jokes that implies.

**106 · Conspiracy theory** — uncommon · 15mm · Claude
Crazy dots connected into a conclusion. Two variants: a real-world theory, either
invented or one that genuinely exists; or a conspiracy about the receipt system
itself, fed by real archive patterns from slot 113. The pattern may be true, the
conclusion is not, and it is always framed as nonsense.

**109 + 131 · Persona free slot** — rare · 40mm · Claude
The persona drops the format entirely and talks about whatever it likes. It may
introduce itself, stir drama with another persona, address the reader directly,
or taunt them with slots they have never received.

**78 · Fake product line item** — rare · 15mm · Claude
An infomercial for something that ought to exist, priced, as a receipt row.

**79 · Receipt for the receipt** — n/a · folded into the footer itemization,
`SYSTEM.md` §2.1.

**137 · Changelog** — rare · 15mm · Claude
Announces a slot appearing for the first time, mixed with straight-faced nonsense
entries: `removed herobrine`, `nerfed mosquitos`, `gained sentience`.

---

## SELF AND PAPER-CRAFT

**48 · Journaling prompt** — uncommon · 35mm · Claude
A prompt with three ruled blank lines to write on.

**49 · Big three checkboxes** — common · 20mm
Three empty boxes, filled in by hand. Deliberately analog.

**50 · Mood scale** — uncommon · 8mm
One to five, circled. The pattern emerges across kept slips.

**51 · Micro-dare** — uncommon · 10mm · Claude
Take the long way home. Talk to a stranger. **The persona renames it every single
time** — `TODAY'S MISSION` and the like. It is never printed as "micro-dare".

**87 · Blank comic panels** — rare · 45mm
Three empty panels **with a drawing prompt**.

**55 · Reversed-out black panel** — rare · 30mm · renderer
Solid black with the text knocked out white. Heavy on heat, so rare keeps it an
event.

**57 · Keep this one** — rare · 5mm
A mark on receipts worth photographing before the thermal paper fades.

**58 · Micro-print** — rare · 5mm · renderer
Legible only through a phone camera zoom.

**59 · Ruler down the edge** — rare · 0mm · renderer
Runs alongside existing content, so it costs no extra paper.

---

## TRIVIA AND NUMBERS

**43 · Year-percent progress bar** — uncommon · 8mm
**44 · Days alive** — uncommon · 5mm
**45 · Countdowns** — uncommon · 8mm · config-maintained list
**47 · Today's dice roll** — uncommon · 5mm — a seed for undecidable decisions

**46 · Machine facts** — uncommon · 8mm · local
One true fact about the printer, the paper, or the code that made the receipt.
Thermal paper carries no ink — the paper itself darkens under heat. This page is
576 dots wide. The TM-T20II prints at 200mm/s. This receipt was composed in HTML,
photographed by a headless browser, and thresholded to pure black and white.
Deadpan and self-referential. **Never about how much paper is left.**

Facts must be **true of the machine currently attached**, not inherited — the
printer changed once already, taking the old speed and width figures with it.
Pull anything numeric from `printer.base`, never from memory.

---

## LEGENDARY — 1 in 25

Formats are pre-built; the content inside them is written fresh. Full list in
`SYSTEM.md` §4.1.

**134 · Full persona takeover** — legendary · varies · Claude
The spine is abandoned entirely and the persona talks about whatever it wants.

**144 · Full short story** — legendary · 60cm–3.4m · public domain
A complete story. The pool is weighted: about 90% land at 1,500–2,500 words, and
about 10% run up to 6,000 — making the longest ones roughly a once-a-decade event.
Weighting table in `SYSTEM.md` §4.2.

**118 · One-day-only slots** — legendary · varies
Solstice, birthday, 29 February. These bypass the draw entirely.

---

## CUT — do not rebuild

| Reason | Slots |
|---|---|
| No Google Calendar | 6, 7, 8, 9, 21, 39, 80, 100 |
| Not wanted | 20, 27, 28, 40, 41, 42, 52, 54, 56, 61, 64, 65, 68, 71, 81, 82, 83, 88, 91, 92, 97, 105, 107, 108, 119, 124 |
| Folded into the coupon | 74, 75, 76, 77, 86 |
| Answers now print same-day | 18 |
| Too long, replaced by 147 and 144 | 19 |
| Littering | 89 |
| Needs an always-on daemon | 120, 121, 122 |
| Never recommended | 127, 128 |
| Impossible on paper | 129 |
| Built, then cut on paper | 53 |
| Too fiddly to be worth it (hand-authored fold diagrams) | 90 |

- **106 is not cut.** The calendar version died with the rest of the calendar
  family, but it was rewritten without one and survives under Generation.
- **53 (fold-to-reveal) was built, printed, and cut.** The mechanism worked:
  question and answer set symmetrically about a marked line, so one fold brought
  them together. The problem is that it conceals nothing. The answer is printed
  on the same piece of paper and is readable by turning the receipt round, so
  folding is not a reveal, it is an inconvenience — and it costs 52mm, most of
  it the blank gap the geometry needs. Slots 14, 16 and 17 already do
  same-day answers properly, upside-down at the footer, which is out of the way
  and a convention people know from puzzle books.
  It would be worth rebuilding only if the fold did real work — each glyph split
  so that half the strokes sit above the line and half below, illegible until
  the two halves meet. That is a genuine rendering project and may not survive
  thermal printing at all.

- **129 (Wordle)** is the only genuine impossibility: it needs turn-by-turn
  feedback, which paper cannot give. Slot 15 is the paper-native equivalent.
- **123's "yesterday's top track" half** is cut, since it needs OAuth. The
  Spotify Code half survives.

---

## Approved, but specified in `SYSTEM.md`

Mechanisms rather than content slots, so they have no entry above.

| ID | Name | Where |
|---|---|---|
| 117 | Rarity tiers | `SYSTEM.md` §4 |
| 118 | One-day-only slots | `SYSTEM.md` §4 |
| 126 | Weekday variants | `SYSTEM.md` §8.5 — tonal only |
| 135 | Rarity stars | `SYSTEM.md` §2.2 — every receipt |
| 136 | Failure report | `SYSTEM.md` §7 |
| 139 | Monthly report | `SYSTEM.md` §8.3 |
| 140 | Legendary formats | `SYSTEM.md` §4.1 |
| 142 | Fun fact | duplicate of 130, merged |
| 79 | Receipt for the receipt | `SYSTEM.md` §2.1 |
