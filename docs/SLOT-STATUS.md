# SLOT-STATUS.md — What is built, how each one works

`SLOTS.md` is the catalogue of what the receipt *should* print. This is what it
*does* print, with a paragraph per slot on how it actually works and what is
left to do. Sections follow the catalogue's families.

Keep this current in the same commit as the work. `python tools/slotcheck.py`
prints the machine-checkable half (coverage, tiers, a fixture smoke test); this
file holds the half a tool cannot know.

**Coverage: 84 of 94.**

| | Built | Catalogue | Notes |
|---|---|---|---|
| spine | 7 | 7 | complete |
| common | 16 | 16 | complete |
| uncommon | 33 | 37 | |
| rare | 25 | 28 | 90 origami cut; 60 jigsaw on hold |
| legendary | 3 | 3 | complete; 13 of 22 formats |

Not built: 13 Lichess, 29 film frame, 45 countdowns, 58 micro-print, 60 jigsaw,
70 headline from 100 years ago, 123 Spotify Code, 145 street guess (1 and 79 are
the template itself). See ROADMAP.md for why each is waiting.

Each header gives the slot's declared tier and worst-case paper, as in its
`SlotSpec` (`[slots.tier]` / `[slots.paper_mm]` in config.toml override both).

---

## Status key

| | |
|---|---|
| **live** | built, verified on paper, nothing outstanding |
| **built** | built and rendering, not yet seen on paper |
| **partial** | works, with a known gap recorded below |

---

## Spine — prints every day

**2, 3, 4, 5 · Weather** — live
Four slots, one Open-Meteo call shared through `ctx.shared`. No key needed.
`past_days=1` fetches yesterday's actuals alongside today's forecast, so the
temperature delta and the daylight change work on the very first run rather than
waiting a day for our own cache to fill. Every success is cached; a network
failure serves the last good payload flagged stale. The verdict is composed from
independent clauses, never a temperature ladder, and has a bland-day fallback so
it never prints nothing.
**The day's high and low are a UI element, not prose.** They get their own
bordered pair at nine pixels above body size, so the two numbers you actually
look for are the easiest thing in the section to find, and the narrator is told
they are printed beside its text and not to state them. It writes about what
they *mean* instead.
Whole degrees, except when both round to the same figure: a day running 17.6 to
18.4 is real and would print as "18 / 18", which reads as a fault. One decimal
only when the rounded figures collide keeps the common case clean and the odd
case honest.
**Each persona draws the weather its own way** (`render/weather_layouts.py`),
from the same facts - slots 2-5 compute everything and a layout decides nothing:

| Layout | What it shows | Personas |
|---|---|---|
| chart | the hourly curve, rain rising from the floor, night in the axis | accounts-receivable, ops-officer, bootleg-tape |
| parts | morning / afternoon / evening / night as four cards, closed by a TAKE row | daily-roll, all-nite-diner, stage-manager |
| threedays | yesterday, today and tomorrow on one temperature axis | time-traveller, noir-detective, commentary-box |
| dial | a 24-hour clock: ring is warmth, spokes are rain | victorian-clerk, oracle, first-mate |
| counted | the day as tallies of hours | monkey-astronaut, mimic, the-machine, revolutionary |

Set with `weather = "dial"` in `personas.toml`; absent or unknown falls back to
the chart, and a layout that raises falls back to the plain arrangement in the
template. The hourly series rides in `SlotResult.extra` - data the page uses and
the narrator never sees, since twenty-four figures in `brief` would be spent
tokens and an invitation to describe them. Condition marks (fog, drizzle, sleet,
thunder) come from Open-Meteo's own `weather_code`, not a guess from cloud
cover. Every class in the layouts is `wx-` prefixed: an unprefixed `bar` would
inherit a theme's own `.bar` and paint every temperature bar solid.
**The offline fixture** is a committed Open-Meteo payload,
`assets/fixtures/openmeteo-london.json`, of exactly the shape the live call
returns: two days of hourlies from `past_days=1`, so the delta and daylight
slots are exercised rather than skipped. `openmeteo.sample()` slides its dates
onto whatever day is being rendered, and the four slots share it through
`ctx.shared` by the same helper the live fetch uses, so a fixture render runs
the real slicing, signals and composition — only the source of the JSON differs.
The cache fallback inside `openmeteo.get()` is deliberately **not** the fixture
path: it reads the store, so it would hand back real weather on a machine that
has run before and raise on one that has not. It also means invented weather can
never leak into a live morning.
*Deviation from SLOTS.md:* the sample is one fixed day, London, early September —
a cool morning, a wet band 13:00–17:00 peaking at 80%, wind to 31km/h, three
degrees down on yesterday. It does not vary by date, so a contact sheet shows the
same weather on every simulated day. That is intentional: the sheet is for
checking layout and rotation.

**10 · News ×3** — live
Hand-parsed RSS and Atom over the `[[news.feeds]]` in config (your own list goes
in `config.local.toml`), fetched in parallel and each cached separately so one
dead feed is skipped rather than fatal. Two diversity constraints: one headline
per outlet, and at most `[news] grim_max` grim headlines (2 of 3) — capped
rather than ranked down, since ranking only promotes the next disaster.
*Serious news is not avoided* (2026-10-28): the cap was one and the ranker was
told "at most one bleak story" and "a story close to their life beats a
summit", and real mornings showed important news losing to curiosities.
Softening the prompt alone was not enough - on a day with a deadly train crash,
a Corsica vote and a Paris march route, it still chose three hobby stories - so
one pick is now, by default, the day's most important world, French or Paris
story, grim or not, unless nothing is genuinely important. The grim word list is death and disaster only - "shot", "strike", "fire"
and "arrested" were in it and caught a game-winner, a transport strike and a
coach being fired.
**Ranked by reading the profile as prose** (`narrator.rank`, at `effort: low`,
indices only - it never sees a headline it could rewrite). Keyword overlap
against the `## Keywords` block of `data/profile.md` is the fallback: offline,
no API key, or a failed call. It is blunter on purpose - prose defeats it, and
"acquisitions, unless the thing acquired is interesting on its own" puts
*interesting* into the anti-list. The `## Keywords` block is kept out of what
the model reads, so it sees the sentences and their qualifications.
**The diversity rules stay in Python**, applied to whichever order comes back,
and a short or duplicated pick is topped up from the keyword ranking: a model
returning two disasters from one wire does not get to make that a bad morning.
**Feeds are configured, not just listed.** Each has a `name` to print (feeds
call themselves "Latest Updates", "Blog" or nothing; `rss.publication()` is the
fallback, taking the section off a channel title), a `weight` for how good the
outlet is for this reader (0.5 filler, 1 solid, 1.5+ the best of its kind), and
an optional `max_age_hours`, so a weekly feed is not invisible behind a 36-hour
window. Headlines print in whatever language they came in; the gloss is asked
for in English.
**A fair look on a fixed token budget.** The ranker reads `candidates` (48)
items, never more, each summary cut to `summary_chars` (120). `pool()` gives
every feed one seat, then shares the rest by D'Hondt on the weights, so a feed
posting twice a day is in front of the ranker as surely as a wire posting a
hundred times, and a quiet feed's spare seats go to the others. Within a feed
the freshest go first, except Hacker News: its highest-ranked posts, by points.
**A one-line gloss under a headline that needs one** - who someone is, what a
project is, the number, the cause, the detail that makes the story make sense.
It comes from that item's own feed summary, never from the model's own
knowledge. Restating the headline is forbidden outright, and a gloss is the
default: an empty string needs a reason. Length is enforced, not only asked
for: 110 characters, cut at a word. **Without the ranker** a gloss is still
printed when the feed or page offers a first sentence short enough - quoted,
never composed.
**Hacker News items get their article read** (`sources/article.py`). The linked
page's own `og:description` (or `description`, or its first real paragraph; a
GitHub repo's API description, since GitHub's meta is boilerplate), and when the
page says nothing, the poster's text or the top comment - labelled as a comment
so the gloss can quote it as the comment's and never pass it off as the article.
Only for HN items in the pool, read in parallel, cached per URL so an offline
morning still has them. The pages are read in worker threads and the cache on
the main thread, because a SQLite connection refuses any thread but its own. HN
descriptions get 80 more characters than a feed summary: a description cut
mid-clause invites the gloss to finish the sentence from memory.
**Layout: a headline, and a note under it.** The headline verbatim, then a ruled
note carrying the source as a label line with the gloss under it. The source is
a block of its own, not a run-in prefix, because several themes set the whole
page in capitals and ship no bold, and on those a label and the sentence after
it would read as one. An aggregator's label says where its link goes - `HACKER
NEWS · NEWS.MIT.EDU`. An item is two children, always: the marker the template
prints, and ONE block holding the headline and everything beneath it - themes
lay an item out as a flex row or a two-column grid, and a third child lands in
the marker's column. The base stylesheet owns `.news-body`, `.news-note` and
`.news-src`; themes restyle them freely.
**It remembers what it printed** (`news:printed`, keyed by day, `memory_days` =
5). The same link or title never prints twice - a 36-hour window would otherwise
reprint yesterday's - and the ranker sees the list, so the same story under a
new headline is skipped too, unless it has genuinely moved on: then the label
reads `FOLLOW-UP FROM YESTERDAY` (or the weekday). Written on real mornings
only, and never by a preview after the day's receipt printed (`printed_already`).
*Watch:* the narrator-stays-loose ruling (below) covers colour, not figures; if
a figure ever arrives in a gloss that was not in its summary, tighten the prompt
rather than the summaries.

**11 · Coupon** — live
**The persona's own object.** Deviates from `SLOTS.md`, which rotates a
bureaucratic form every day: every persona declares its coupon in
`[persona.blocks]`, so the slot draws no form or subject of its own, which would
only contradict it. The persona's block says what the coupon is; the slot only
asks for something specific and never idleness. The narrator writes the fine
print as well (`fine_print` in the brief adds a `fine` field to that slot's
schema, `narrator.build_schema`), so a block that says what its footnote is gets
exactly that - the OPS recall condition, the Clerk's clause you should not test.
An empty string means no fine print. Six plain offline coupons remain for a
morning with no narrator, and a persona's own offline copy replaces them on its
page.
Variety rests on the persona rotation and the blocks themselves. Where a
persona's own coupon would repeat, its block draws a pick per appearance instead
(SYSTEM.md 3.8, block tables): the Detective's contact, the Monkey's ration, the
Time Traveller's item, the Revolutionary's cover name, Accounts Receivable's
form.
**The First Mate's coupon is a collection.** Each of her mornings prints one 25mm
piece of a treasure map, drawn in Python, beside a three-line ship's log ("DAY
1203: ...") of how the crew came by it. Nine pieces make a map and six maps are
listed, with the X's own piece last (SYSTEM.md 3.8, the treasure hunt;
`render/treasure_map.py`). The narrator writes the log, but the piece is a fact,
told to it as one. The piece measures 200 x 200 dots in the 1-bit raster, exactly
25.0mm, and is never scaled or turned. The Mimic wearing her prints a forged
piece, tagged "?", rather than a real one out of turn.

**146 · Absurd legalese** — live · occasional · 15mm
Fires on about a third of receipts. A clause plus a footnote that undermines it;
the footnote is the joke, and the narrator writes it (`fine_print`, as the
coupon does), so a persona block that names its footnote gets exactly that. The
canned clause-and-footnote pairs remain as the offline copy. On a `speakers`
persona the footnote is set as a turn like the body.
Most personas' legalese is not legalese at all (block tables, SYSTEM.md 3.8): a
case report, a corrections column, a health inspection card, flight rules,
release notes. The slot's Pratchett instruction still goes first and the
persona's form follows; the footnote-undermines-the-clause shape survives in
nearly all of them as the pencilled line, the shout-outs, the office's ruling.

---

## Weather and sky

**35 ISS passes, 36 visible planets, 38 star chart** — built · rare · 24–82mm
Computed locally with PyEphem (`sources/sky.py`), so planets and stars need no
network and cannot go stale. Only the ISS reaches out, for its orbital elements
from CelesTrak, and caches them.
*"Tonight" is an hour after sunset, not a clock time.* 21:00 is broad daylight in
June at European latitudes and four hours into darkness in December; an hour
after sunset is when the brighter objects become visible in every season, and it
needs no timezone because ephem computes sunset for the observer.
*A visible ISS pass needs three things at once* - the station above the horizon,
the station in sunlight, and the observer in darkness. A naive pass predictor
reports only the first, and most of those passes are invisible. Checked at the
peak.
*East is on the left of the star chart*, because it is held above your head and
read looking up - the mirror of a map. Get it backwards and the chart is exactly
right and useless. Checked against the real sky: the Summer Triangle near the
zenith, Arcturus setting in the west and Capella rising in the north-east, as it
should be on a mid-September evening at 49 degrees north.
*Nothing up returns None.* On many evenings no planet clears the horizon murk
and no pass happens in darkness; that is true and is also a waste of paper.
*No bundled ISS elements for the fixture.* The orbit is re-measured constantly,
so a TLE in the repo would be months stale within a season, and `--offline`
really prints - no pass shown is true, a confident wrong pass time is not.

**37 · Moon phase** — live · common · 24mm
Pure arithmetic, no network, cannot fail. Drawn as SVG because it is a
hard-edged shape that thresholds cleanly. The dark side is hatched: at 4%
illumination a correctly drawn moon is a black blob, technically right and
visually broken.

**72 · Friend timezones** — built · uncommon · 70mm
One row per zone in `TIMEZONES` (.env, read by `config.friend_timezones()`),
west to east: the local time in a box, the city, how far ahead or behind here
it is, awake or asleep, and the temperature there now. Under each row is a bar
of today here, midnight to midnight, with their night in black and a rule at
the present moment. The bars share one axis, so the nights march left from
west to east and a white gap is an hour you could call.
**The clocks are Python's and cannot fail.** Each zone goes through `zoneinfo`,
so the weeks when Europe and North America are out of step on summer time come
out right. Windows ships no time zone database, so the `tzdata` package is in
`requirements.txt`; without it every lookup fails. The city printed is the
zone's own name (America/New_York as New York). A zone the database does
not know is dropped alone, and the others still print.
**Awake means 07:00 to 23:00 where they are**, `[timezones] awake_from` and
`awake_until` in config.toml. It is a guess about other people's sleep, so the
fine print states the rule, and "asleep" reads as "it is 01:00 there" rather
than as a claim about anyone's habits. Asleep times are reversed out, so the
sleepers can be picked out down the left edge before anything is read.
**A temperature that cannot be fetched is left out, never borrowed.** One
Open-Meteo call (`current=temperature_2m`, several locations at once) carries
every city's reading. If it fails, every clock still prints and only the
degrees go: a cached reading from yesterday would be a confident wrong number
beside a correct time. Coordinates are the opposite, because a city does not
move: each zone is geocoded once, cached through `sources/http.py`, and kept for
good. The first result *in that zone* is taken, not the first result: a city
name has namesakes, and only one of them is in the zone.
**What time it is.** A real morning reads the clock when the slot runs. A
simulated `--date` and the fixture read 07:00 that day, the print time, so a
preview shows the clocks as they will stand when the receipt prints. The offset
from here comes from the machine's own zone on that date, so a December
simulation gets winter time at both ends.
**The fixture** computes real clocks and takes its temperatures from
`assets/fixtures/openmeteo-friends.json`, a real reply for a handful of major
zones (those in `.env.example` among them), through the same parsing as the
live reply. It reads no store. A zone missing from the sample prints without a
temperature.
**Verbatim.** Times and temperatures are facts (invariant 8). The narrator gets
who is awake and who is asleep to name the section from, and writes nothing
into it.
**70mm, not the catalogue's 20.** With five zones, measured in all sixteen
personas, it runs from 54mm (the Revolutionary) to 67mm (the Bootleg Tape); the
claim adds headroom for a narrated header that wraps. Each zone is a row of
about 12mm, so adding a sixth means raising `[slots.paper_mm] 72` too.

---

## Puzzles

Every answer prints the same day, upside-down at the footer (`SlotResult.answer`,
`.answers` in the base template). Above the tear line, so taking the coupon does
not take the solutions with it.

**14 · Nonogram** — live · common · 92mm
Date-seeded, 5×5 most days and 10×10 about one time in four. The generator draws
a random pattern, derives the clues, then **runs a line solver over its own
output and keeps only puzzles that pure deduction can finish** — for each line it
enumerates every arrangement consistent with what is known, keeps the cells all
arrangements agree on, and repeats to a fixpoint. A grid the solver finishes has
exactly one solution and needs no guessing. Random patterns frequently fail this
and there is no way to tell by eye, so without the check the slot would sometimes
hand over an unfinishable puzzle on paper. Checked: 120 of 120 generated puzzles
solvable, about 20ms each.

**15 · Connections-style word grid** — built · common · 66mm
Sixteen words, four groups. The puzzle is a **fact** - it must have exactly one
valid grouping - so it belongs on the Python side of the line: a model inventing
sixteen words will occasionally produce a grid where a word fits two categories,
which is unsolvable on paper with no way to check.
*The difficulty and the risk are one mechanism.* Groups drawn at random will
sometimes both want a word, which is the whole pleasure when deliberate and a
broken grid when accidental. Each of the 44 categories declares its **decoys** -
words elsewhere in the bank it could fairly claim - and the draw rejects any set
where two groups compete. Checked over 300 grids: sixteen distinct words every
time, all 44 categories reachable.

**16 · Micro-maze** — live · uncommon · 85mm
Randomised depth-first search, which gives long winding corridors rather than
the lattice that Prim's and Kruskal's produce. The result is a perfect maze —
fully connected, no loops — so the solution is unique by construction and a
breadth-first search recovers it. The footer copy inverts the line weights:
hairline walls, fat path. At equal weights the route is indistinguishable from
the corridors and the answer reads as a second maze.
*Sized on paper:* 15x11 at 30px, about 42mm of maze - big enough to trace with a
pen, small enough not to crowd the page. Cell size is the dial, not cell count:
fewer cells stops it reading as a maze long before 30px stops being a
comfortable corridor.

**17 · Cryptic crossword clue** — built · uncommon · 28mm
The cheapest puzzle on the receipt and the one that fits when the budget is
tight. The answer prints upside-down **with its parse**, because a cryptic whose
answer you cannot reconstruct is just a fact you were told.
*The wordplay is machine-checked.* Each clue carries its device and fodder as
data, and `verify()` confirms the mechanism genuinely produces the answer:
anagram letters really rearrange, hidden words really are hidden, reversals
really reverse. Anything that fails is dropped from the pool rather than
printed. A wrong anagram is invisible on the page and costs someone ten minutes
before the parse gives it away. `tools/crypticcheck.py` runs the bank - 43/43
verify, 16 anagram, 9 reversal, 8 hidden, 10 double definition.

---

## Series

**The series engine (`slots/series.py`)** - SYSTEM.md 5, built as a base class
rather than central code. One series at a time; a series slot drawn while
another runs drops out of the day. Rare to start, then each tile pins the next
morning, so a running series never has to win the draw again. Three-week
cooldown after one finishes; alternation when there is more than one series.
**Draw first, commit after:** a tile that cannot be drawn (no network, no cache)
is printed tomorrow rather than consumed. Only a real morning advances, and a
rerun of the same morning reprints the same tile.

**Pinning.** A slot that has started something it must finish tomorrow pins
itself to that date, and the selection engine prints it then regardless of tier
or recency. A pinned slot is a continuation rather than a draw: it goes on top of
the day's normal three to five, so being mid-recipe does not cost the morning a
section, and it is removed from the pool so it cannot be drawn twice. *Only a
real morning pins*: a `--date` simulation that pinned a real future date would,
when that date arrived, print the second half of a meal nobody was told to shop
for.

**62 · Growing city map** — built · rare · 100mm
A 5x5 grid printed in a spiral from the centre, so piece one is home and the
city grows outwards; a reading-order map would spend its first week on a corner
nobody walks to. Each piece is four OSM tiles at zoom 17 composed to 512px (about
400m a side, street names at a printable size), dithered - the style is soft
colour fills a threshold would erase - with corner marks, a big grid reference,
and a 5x5 progress grid. OpenStreetMap's tile policy is followed: identifying
User-Agent, four tiles a morning, every tile cached on disk forever
(`data/tiles/`, gitignored because it is the home neighbourhood), attribution on
every piece. The fixture is a drawn street grid, never a real place.

**63 · Two-day recipe** — built · uncommon · 44mm
Day one prints a shopping list with tick boxes and does not name the dish; day
two prints the recipe, pinned. Exempt from the one-series rule.
*The recipe is Python's, not the narrator's.* Quantities, oven temperatures and
cooking times are facts someone follows with real food, and an improvised
temperature for chicken is worse than a ruined dinner. Seven dishes written out
in full, printed verbatim.

**60 · Jigsaw** — on hold. The engine supports it; the image pool does not exist.

---

## Input loop

One mailbox, read over IMAP, routed by subject (SYSTEM.md 6): seven slots, one
collector, no hosting and nothing to log into.

**`sources/mailbox.py` reads, and only reads.** The inbox is opened readonly -
nothing is deleted, moved or even marked read, because a slot that failed to
print should be able to print tomorrow. Subject prefixes route
(FEEDBACK/LETTER/PHOTO/FRIEND/TONIGHT/IDEA, after any Re:/Fwd:), anything else
is left alone, and each slot records the message id it printed so nothing is
delivered twice. One connection a morning: the first slot to ask pays, the rest
read `ctx.shared`. An unreachable mailbox returns no mail, and the slots that
need it drop.
Bodies are trimmed at the first quoted line or signature, because a phone
quotes the whole receipt back. PHOTO attachments are saved under `paths.photos`
(gitignored) to resurface later as printed photos.

**67 a line from a friend, 69 note from 11pm-you, 22 letter delivery** — built
· uncommon. Print the sender's own words verbatim - a persona rewriting a
friend's message in voice is the worst failure available to these slots. 22 is
one slot in two states: with no letter old enough (90 days) it prints the QR
invitation instead, which is the same slot keeping its promise.

**12 · Prompted feedback** — built · uncommon · 45mm
Names a section that really printed, on the day it printed, from the archive -
"was Sunday's nonogram any good?" gets an answer where "how was your receipt?"
gets nothing. No archive, no section.
*The question is the body, so the persona writes it*, which makes this the one
input slot that is NOT verbatim - and therefore the QR lives in `fine`, a field
the narrator has no schema entry for. A body the model may write into is a body
it could replace the code with. An unanswered reply is handed over in the brief
for the persona to agree with or argue with, and marked used so it is answered
once rather than brought up every morning.

**66 · Photo assignment, 73 · Dead drop** — built · uncommon · 46mm, 47mm
66 draws from fifteen assignments about attention rather than photography,
recently-used suppressed. 73 puts a point at a random bearing 500-2000m from
home and prints the coordinates large with a `geo:` QR beside them, since a code
that fails to scan in a kitchen should not cost the section.
*Deviation:* SLOTS.md files 73 as "a variant of 66" with no tier. It is
registered as an uncommon slot in its own right - it is drawn, costed and
suppressed separately, and a variant sharing 66's draw would print two
assignments on one morning. This is the tier mismatch `slotcheck` reports.

**141 · New slot suggestion** — built · rare · 45mm
Asks the narrator for a section that does not exist yet, handing it the names
of all that do, and prints a QR for the verdict. Proposals are kept in the store.

---

## Discovery and culture

**23 · Painting of the day** — live · uncommon · 80mm
Three museums rotated by day: the Art Institute of Chicago, Cleveland, and the
Met. All open, no key. The Rijksmuseum is the catalogue's fourth and is left out
deliberately — its API now needs a registered key, and a slot that needs a
secret breaks silently on a machine where the secret was never set. Providers
fail independently: if today's museum is down the slot walks to the next rather
than dropping.
**Dithered, not thresholded** — the opposite of tarot and XKCD, and the clearest
illustration of that rule on the receipt. A painting is continuous tone;
thresholding it leaves a blot. Contrast is scored before printing and a flat
image is redrawn from another museum, because the source is a random draw from a
million objects and nobody has looked at it.
Cleveland's open-access set is filtered to paintings and drawings: unfiltered it
is mostly manuscript folios and decorative objects. The Art Institute throttles
with a **403**, not a 429, which reads as a permissions bug and is not one; its
identifying header is sent and the provider walk absorbs it.

**24 · Dev knowledge** — built · uncommon · 22mm
Thirty-odd entries across git, shell, CSS, browser APIs and editor tricks. The
day picks a **kind first**, then an entry within it: drawing straight from the
list would weight the slot towards whichever category has most rows. The snippet
is verbatim and set in the monospace — a rephrased command is a broken command.

**25 · Book quote** — built · common · 36mm
**Scraped from Goodreads, as the catalogue specifies.** Goodreads shut its public
API in December 2020, so the public quote pages are the only source.
**The pool is the reader's list in `data/books.txt`** (gitignored; the template
is `books.example.txt`) - one `Title — Author` per line, pasteable straight from
a Goodreads shelf. Nothing in code changes when a book is finished.
**Within Goodreads' published crawl rules.** Its robots.txt (as of September
2026) says `Allow: /work/quotes` for every agent and disallows only the quotes
RSS feed. An identifying user agent, and a five-second floor between any two
requests - the crawl delay Goodreads publishes for Bing, applied to everyone.
**Two requests per book, because search is not specific.** Searching for a title
returns quotes from the author's other books too. Search is used only to find
the book's `/work/quotes/<id>` page, and the quotations come from that, filtered
to the title again.
**Goodreads is behind AWS WAF, and the scraper stops at its challenge.** After
five requests in about thirty seconds every response becomes a 2.4KB WAF bot
challenge. The scraper detects that page by name, records a cooldown, and stops
- both the harvest tool and the morning slot respect it. It does not solve,
evade or wait out the challenge: no headless browser running its script, no
borrowed browser headers, no retry loop.
**So the work is done slowly, ahead of time.** `tools/harvestquotes.py` trickles
through the list a book every two minutes, stops at the first challenge, and
resumes later from the first uncached book. The morning makes at most one live
request pair, only for a book whose cache is missing or a season old. The
quotations are cached in `data/quotes.json`, which is gitignored: they are other
people's copyrighted words, scraped for a personal receipt.
**Weighted by author, not by book.** A read list is dominated by long series,
which would take a fifth of all mornings under a uniform draw. Each author
carries the square root of their book count, so an eight-book series comes up
about three times as often as a one-off, not eight. Recently quoted books and
quotations are suppressed; within a book, quotations are weighted by the square
root of their likes.
**Quiet on a bad morning, loud when it has really broken**, both halves of the
spec. One failed fetch serves a cached quotation silently. Three consecutive
failed mornings turns the section into the escalating in-persona bulletin from
SYSTEM.md 7 - AGENT COMPROMISED - which grows more apocalyptic with each morning
until a fetch succeeds. With no failure and nothing cached, the section drops
rather than announce an outage that never happened.
**The quotation is verbatim and the attribution is Python's** - both come from
the scraped page, so the narrator only names the section.

**26 · ASCII art** — built · common · 76mm
About 1,700 pieces harvested from asciiart.eu by `tools/harvestascii.py` into
`assets/ascii/harvested.json`, plus the hand-placed `.txt` pieces.
**Tagged by the site's categories**, through `assets/ascii/sources.toml` (persona
tag -> sub-categories, plus title keywords), which is a person's judgement of what
a piece is rather than a guess from its characters. Every persona tag has its own
supply: the thinnest-served personas match about 70 pieces, the best-served 370
and more.
**Filtered for paper:** pure ASCII only, 12-74 columns by 5-26 rows, and at
least a quarter of the ink in dense characters so it survives the threshold.
Wide pieces are set smaller rather than wrapped - a CSS `clamp()` against the
section body's own width in container units, never below the 12px floor - and
the limits are re-checked at load, so tightening one needs no re-harvest.
**Four draws in five share a tag with the persona**; the fifth is anything. The
last 60 pieces printed are skipped. Usenet-era art is sometimes crude, so the
sub-categories that lean that way are left out of `sources.toml` and a title
blocklist in the harvester catches the rest; letter-shaded photo conversions are
dropped too, since they print as a jumble of characters. The artist prints as a
small credit bottom-right, unless the site lists them as unknown or the piece is
already signed. Rendered in the embedded monospace, never the persona face.
*Deviation from the catalogue:* it says Claude picks the piece. The narrator
returns a header and a body string and has no way to hand back a choice, so the
match is configured instead.

**30 · Wikipedia rabbit hole** — live · common · 53mm
Pool is `assets/unusual.json`, 3,706 articles harvested from
`Wikipedia:Unusual_articles` by `tools/harvestunusual.py`. Not the
random-article endpoint, per the catalogue: that returns geographic stubs.
Harvested and committed rather than scraped each morning, since wikitext parsing
at 07:00 is a morning that breaks when the table markup changes. Carries a QR to
the article. The editors' own one-line descriptions are kept as the offline
fallback and are frequently better than the article's opening sentence.
*Excluded from the harvest:* the Death subpage, the Removed subpage (articles
editors **delisted**), and the Categories meta page.

**31 · Untranslatable word, 32 · Etymology, 103 · Invented word** — built ·
uncommon / uncommon / rare · 22–26mm
One module, `slots/lexicon.py`, because 32 is true and 103 is false and the
catalogue requires them to be **distinguishable at a glance**. Keeping them
together is the cheapest way to stop the marking convention drifting.
*The mark is in the stylesheet, not the text.* Asking the narrator to mark its
own inventions works most of the time, and most of the time is not a marking
scheme; putting the dagger in `body` is worse, because 103's body is
deliberately narrated, so the rewrite that makes the section good is the same
rewrite that silently removes the mark. `.slot-103` adds it, and no rewrite can
reach it.

**33 · Logical fallacy or cognitive bias** — built · uncommon · 29mm
Twenty entries, each a name, a definition and a *trap*: a concrete, ordinary
situation it shows up in. The narrator names the bias briefly and spends the
rest on where it will catch the reader today - a bias plus the shape of the trap
is something you can notice happening, where a bias defined is a flashcard.

**34 · What's in season** — built · uncommon · 20mm
A month lookup table rather than an API: the good sources are national and
either paywalled or unstructured, and this genuinely changes once a decade.
Three vegetables rather than five, because a list of five is a stock check and
three is a suggestion, plus the one thing worth going out of the way for.
*Hemisphere is derived from the configured latitude, not assumed*: claiming
asparagus in April for a reader in Melbourne would be wrong in the one way this
receipt may not be. Below the equator the lookup shifts six months and the slot
says so.

**84 · Wallet cheat sheet** — built · uncommon · 58mm
Twelve cards, rotated with recent ones suppressed, because the catalogue's
instruction is "rotate widely" and a cheat sheet always about one kind of thing
is a card you stop reading. Rendered as a two-column table in the mono face
rather than as prose: these are things to look at, not read, and a table of
facts can be checked line by line in a way a paragraph cannot. Dashed border,
because it is meant to leave the receipt.

**85 · A line of sheet music** — built · rare · 70mm
*Deviation:* name-the-tune instead of "the persona chooses the song". The
narrator cannot hand back a choice, a melody it wrote itself would be a wrong
note from a wrong fact, and a hidden title gives the reader something to do -
hum it, answer upside-down at the foot. 22 public-domain openings in
`assets/music/tunes.toml`; every tune's bar durations are checked against its
meter by abcjs itself. abcjs (MIT) is inlined only on days the slot is drawn, so
the render needs no network, and scales to the section width.

**125 · XKCD of the day** — live · uncommon · 84mm
A random strip from the back catalogue, not today's — today's is a coin flip and
there are three thousand behind it. Comic 404 is skipped because it does not
exist; that is the joke, and the API 404s for it, which would otherwise look
like an outage. Thresholded as line art with autolevel **off**: a mostly-white
strip has no range to stretch and levelling amplifies JPEG ringing into speckle.
The title text prints as fine print, which is the right register for it — it is
half the comic and there is nowhere to hover on paper.

**132 · Tarot card** — live · common · 87mm
Rider–Waite–Smith 1909, baked to 1-bit at `assets/tarot/`. Chosen on printed
evidence: flat-colour woodcut decks became black masses no threshold could
rescue, while Pamela Colman Smith's heavy black outlines survive
`render.prepare_contour`. 320px wide - exactly on the detail threshold. Degrades
to a drawn frame if the art is absent. Full reasoning in SLOTS.md.

**138 · Wikipedia most-read yesterday** — live · common · 29mm
The catalogue promises "stranger than the news". Taking the top of the chart
does not deliver that: a live sample returned five tennis players and a killing
in the first eight. Two filters — grim articles dropped outright, then the rest
ranked for how much of a rabbit hole they are, using Wikipedia's own one-line
description, which separates "American tennis player (born 2002)" from
"Equations of motion for viscous fluids" cleanly. **The true rank is printed**,
because picking the sixth and implying it was the first is exactly the
embellishment SYSTEM.md 9 forbids — and sixth place with 150,000 readers is the
more interesting fact anyway.

**143 · Wise saying** — live · common · 32mm
The reference shape for a narrator slot. The quotation is verbatim in `body`;
who said it, roughly when, and the theme go in `brief` for the persona to frame.

**147 · Poem of the day** — partial · common · 58mm
Corpus is `assets/poems.json`; add poems without touching code. Verbatim
absolutely — the narrator gets a header only. Line breaks are the poem's, and a
line too long for 72mm wraps with a hanging indent so a wrap is visibly not a
line break.
*Outstanding, two things.* The texts are transcribed and have **not** been
diffed against a canonical source; they print verbatim under a real poet's
name, so that verification is owed. And no Japanese haiku: a modern translation
of Bashō is under its translator's copyright, and a public-domain one has to be
sourced rather than recalled.
*Deviation from the catalogue:* costed there at 12mm, which is about five lines —
true of the two-line Pound and wrong for the twelve-line Housman. Declared at the
longest poem in the corpus, with each result reporting its real height.

**148 · Three-part short story** — built · rare · 295mm
A mini-series on pinning like the recipe, exempt from the one-series rule.
Stories of 700-1,499 words from `assets/stories/stories.json`, split at the
sentence end nearest each third (a paragraph break wins unless it is 5% of the
story away) - splitting only at paragraphs would let one long opening paragraph
make part one twice the size of part three. *Deviation:* SLOTS.md costs it at
40mm, which holds about 80 words - not a real read. The worst part measured is
539 words in the Daily Roll's large face; typical parts are ~400 words.
Idempotent per day.
**The story corpus** - `tools/harveststories.py` over nine Project Gutenberg
collections listed in `assets/stories/sources.toml`: Saki (three), O. Henry,
Poe, Bierce, Chopin, Chekhov in Garnett's translation, Wells. 183 stories kept.
Split at all-caps title headings; the failure designed against is a half story
printed as a whole one, so each book's internal capitals (section titles,
letters, signatures) are listed, roman numerals never split, a heading straight
above another is a title over its subtitle, and `--list` shows every split and
every ending before anything is kept. Stories containing period slurs are
skipped. Drawn by author weighted by the square root of their count, since Saki
alone is half the corpus.

**149 · Joke** — built · common · 24mm
A joke the day's persona would actually tell, not a joke with a voice applied
afterwards. *Two rotating axes:* the day draws a **form** - one-liner, pun,
question-and-answer, definition, misdirection, observational, rule of three,
exchange, mock law, escalation - and an everyday **subject**, from separate
pools, with recent picks suppressed for ten days. Rotating only the form leaves
every joke about the same few things. Subjects are deliberately ordinary - a
joke about a fridge needs no explaining at breakfast.
*Reworked after real mornings (2026-10-28): it often did not land.* Three causes,
three fixes. The brief asked for the persona's "own idea of what is funny", which
got voice with no punchline - now it must make an ordinary reader laugh and the
persona is only the delivery. Anti-joke, shaggy dog and callback were cut from
the forms (*deviation from SLOTS.md*, which listed them): each is built to fall
flat, and alone on the page that reads as a joke that failed. And the narrator
is told to think of five and print the best, with the craft spelled out - one
surprise, at the end, nothing to explain. Subjects gained games, the gym,
running, phones, group chats, passwords and streaming; stationery and shoes
went.
*It remembers what it told:* `after_narration` keeps each printed joke by date,
the last 40, and the next brief carries them as `already_told` - a punchline
retold in a new form is still a repeat, which form and subject suppression
cannot see.

**150 · Horoscope** — built · common · 32mm
A reading for a star sign that does not exist, invented by the persona along
with the sign, so the constellation is as much in voice as the prediction.
*One day in eight uses a real zodiac sign, and that ratio is the design.*
Inventing every single time stops being a joke by the second week because the
invention becomes the format; an occasional real sign resets the expectation and
makes the next invented one land.
*The invention is disclosed in words, not marked with a symbol.* Invariant 8 to
the letter would be slot 103's dagger. Here the disclosure IS the joke - "sign
invented on the premises" is funnier than a glyph and discloses strictly more,
since it says *what* was invented. On a real-sign day the line says "a real one,
for once", which is what makes the ratio visible to a reader at all. Python
picks the territory the sign comes from, the persona names it - which spreads the
inventions out instead of letting them cluster wherever the model's instincts
sit.

**151 · The persona's printed object** — built · common · 110mm · its own model call
The day's persona designs a small printed thing from scratch - a certificate for
eating an egg, a dog tag for a pigeon, a matchbook from a bar that closed - in
its own voice AND its own look. What the object is comes from a 3-6 item list
per persona in `assets/objects.toml`, drawn without repeats (an item's `weight`
makes it likelier). Three in four go fully absurd, the rest nearly straight with
one wrong detail.
**Instructions, not a validator.** A kit of pre-built blocks makes everything
look the same, and a sanitizer that strips the model's CSS is the same
restriction by other means. The model gets the printer's physical limits as
instructions (540px wide, 760px tall, pure black and white, 12px floor, bold only
as `var(--bold)`, only the loaded fonts, no images or scripts) and is otherwise
free. A failure is an ugly section or a dropped one. Only three structural
guards: its CSS is wrapped in `@scope` so it cannot restyle the receipt, scripts
are removed, and it is clipped at 760px. The brief also says outright that the
object carries no real data and must invent none - otherwise a matchbook will
cheerfully print a made-up forecast beside the real one.
**`narrator.design`** is its own call on the ordinary model, since it returns
markup and the main narrator's contract is sentences. 30-85s per object. It obeys
`--offline` and `--no-narrator` through `ctx.shared["may_narrate"]`.

---

## Live search

**93 banger corner, 94 GitHub repo, 96 someone solved something, 98 today's best
sentence, 99 curio price check, 110 explain-at-lunch, 114 a person worth knowing,
130 fun fact** — built · 22–34mm
One module, because they share a shape no other slot has: their content does not
exist until the morning it prints, and the narrator is the collector.
**One call, no agent loop.** Anthropic's server-side web search composes with
the narrator's strict output schema, so a search slot costs no extra round trip.
**Search is attached only when a drawn slot asks for it** (`SlotSpec.needs_search`).
Offering the tool on days when every fact is already in the brief is slower and
is a route for unverified detail onto a factual page.
**The fallback is the previous answer, dated.** These are the only slots with no
content of their own, so there is nothing to degrade to except the last time
they worked. What the narrator writes is cached per slot (`after_narration`); a
failed search serves it back with its age printed. A three-day-old good sentence
is worth printing; a three-day-old sentence passed off as today's is not, which
is why the date goes on the paper. Nothing older than three weeks is served.
*The date leaves with the fallback:* the cached body carries
`SlotResult.fallback`, and when the narrator writes a fresh body `main.narrate`
drops the archive note with the body it replaced. A narrator that skips the
section, a missing key and `--offline` all still print the archived answer with
its age.
*Failure as content, unprompted:* asked for something it cannot verify, the
narrator says so in the section and substitutes a standing fact it can stand
behind (SYSTEM.md 7).
**Cost.** A search morning costs several times an ordinary one. Almost none of
that is the per-search fee: the search results come back into the context, and
input tokens go from about 6,000 to about 21,000.

---

## Search and judgement

**95 what's on tonight, 111 steelman, 116 you were wrong about, 133 check out
this place** — built · 26–38mm · web search
The rest of the search family, on the same machinery. Three of them need to know
where the reader is, so they share a `LocalSearchSlot` base that reads the
location at fetch time and returns `None` when there is none - not a failure,
just no locality to search near.
*95 searches the city, not the suburb.* It reads `QG_CITY` (falling back to
`QG_LOCATION_NAME`), because the weather wants the suburb and the listings want
the city it hangs off - a suburb's own name finds nothing worth the trip. 133
keeps the location name: a place worth the walk should be walkable.
*The steelman is seeded from the profile's anti-list.* That list is the nearest
thing the machine has to knowing what the reader disagrees with, and one term
from it points the search at something specific instead of at "a controversial
topic".

**112 · Connect two headlines** — built · uncommon · 28mm
The only slot that depends on another slot's *output* rather than on a shared
fetch: it takes the headlines slot 10 actually printed, from `ctx.shared`. A
connection drawn between two stories the reader cannot see on the same piece of
paper is an assertion, not a connection. It drops cleanly when the news section
is missing, which is the correct behaviour rather than a limitation.
*It does not search*, despite sitting in this family. Everything it needs is
already on the page, and giving it search would invite it to reach for a third
story nobody saw. The brief asks for a noticing rather than a thesis - a shared
cause is a strong thing to assert about two news stories on no evidence.

**113 · Receipt archaeology** — see "The slots that remember", below.

**115 · Three outlets, one story** — built · uncommon · 52mm · gated by a cheap model · **disabled**
*Disabled 2026-10-28 (`[slots] disabled`)*: it did not work in practice on real
mornings. Left registered so it can come back.
**Paraphrased, but from what the outlets actually published.** The narrator gets
three outlets' real headlines and feed summaries for one event and writes one
line per outlet on how each frames it - what it leads with, which number, whose
words it carries.
**Only printed when it is worth it.** Drawn as an ordinary uncommon, then a cheap
model judges whether any story today is told three genuinely different ways;
three wordings of the same facts are not a section, so the answer is usually no
and the slot drops - the morning prints one slot fewer rather than a dull
comparison. Offline or without a key there is no gate, so no 115; the fixture
returns None for the same reason.
**How the story is found.** `[framing]` is a pool of 17 outlets chosen for
spread - US left and right, UK left and right, France, Germany, Qatar, India,
Hong Kong, Canada, the exiled Moscow Times - read only on days 115 is drawn and
never downloaded twice in a run (`rss.gather(memo=ctx.shared)`).
`sources/framing.py` groups headlines by rarity-weighted shared words, free.
**The gate is `narrator.framings` on `CHEAP_MODEL`, low effort**: it picks the
group and three headlines framing one event most differently, says whether that
is interesting, and gives a one-line `what_differs` the narrator writes from.
About 2.2k in / 0.5k out tokens.
**A claim the summary attributes stays attributed** - the outlet is reporting
it, not making it. Lines are separated by a blank line and the body sets
`white-space: pre-line`, so they print as lines. If the narrator fails, the
three headlines print verbatim under their outlets instead. A story printed here
in the last 14 days is skipped (`framing:printed`), so an ongoing war is not the
slot's permanent subject.

---

## Generation and persona

**78 · Fake product line item** — built · rare · 23mm
Python names the product and sets the price, the narrator writes the pitch. The
name has to be in both the pitch and the line item below it, and the narrator
has no field to return a name in, so letting it invent one would make the two
disagree. The price row is carried in `fine`, which is never narrated.

**106 · Conspiracy theory** — built · uncommon · 28mm
Prefers the machine variant, where the dots are computed from the receipts
table and are therefore genuinely true. Spine sections are excluded from them:
"the weather has appeared 12 times in 12 mornings" is true, trivially true, and
the weakest possible thing to build a conspiracy on. Falls back to a world
variant when the archive is too thin.
*The mark is in the stylesheet and it is ASCII.* Same reasoning as slot 103,
with one addition - an unusual codepoint missing from one persona face prints as
a tofu box, which marks the section as broken rather than as fabricated. This is
the slot where the mark matters most: every other number on the page is real, so
a reader has no way to tell where the reliable part stops unless the layout
says.

**109 persona free slot, 131 direct address** — built · rare · 44mm
The catalogue lists one entry, "109 + 131"; SYSTEM.md 3.3 gives 131 its own
section and behaviour, and two modes drawn at rare as one slot would draw at
twice their stated tier. *The taunt uses the real archive* - "sections never
received" is the registry minus everything that has ever printed, so the persona
cannot boast about a section that has in fact appeared three times.

**The slots that remember: 101, 102, 104, 113, 137.** All five are in
`selection.HISTORY_DEPENDENT`, so none can draw before fourteen receipts are on
file: on a cold start the machine does not pretend to a past it does not have.
**The past is Python's, the voice is the persona's.** Each is built on something
computed from the receipts table and handed to the narrator as fact. The drama
around it is invented and welcome; the record underneath is not, because it can
be checked against the receipts in the drawer. **`data/archive.py` is the one
reader of the archive** - receipt archaeology and the conspiracy slot both call
`archive.patterns()` rather than keeping two copies of the arithmetic that would
eventually disagree about what is true. Only rotating sections count towards
"most drawn": the spine prints every day, and "the weather has appeared on every
receipt" is true, trivial, and not a pattern.
- **101 persona continuity** — uncommon · 22mm. The other personas from the
  recent archive with their real counts and last appearances, for today's
  persona to have a feud about.
- **102 a running bit** — rare · 22mm. Invented the first time it is drawn,
  kept word for word (`after_narration`, real mornings only), and handed back on
  every later draw for a callback. Its unpredictable interval comes free from
  being rare.
- **104 tomorrow's receipt, predicted** — rare · 34mm. Three objective guesses
  (persona, number of sections, whether a rare lands), made by Python so the
  score cannot be argued, then pinned for tomorrow and graded against what the
  selection engine actually drew. The narrator writes around numbers it cannot
  fudge, which is where the jokes come from. Marks are the words HIT and MISS
  rather than tick and cross glyphs, because several persona faces lack U+2713.
- **113 receipt archaeology** — rare · 26mm. One or two true patterns, reported
  as an archivist who has found something and does not claim to know what it
  means.
- **137 changelog** — rare · 26mm. Real debuts (a section printing for the first
  time) shuffled in among nonsense entries. The nonsense lines carry the dagger,
  per invariant 8, because they sit beside true entries in the same list. With no
  real debut the section drops rather than printing pure nonsense, which would
  abandon the premise.

---

## Self and paper-craft

**47 dice roll, 48 journaling prompt, 50 mood scale, 87 blank comic panels** —
live · uncommon ×3 and rare · 20–72mm
One module, because they share a constraint the receipt enforces collectively
rather than individually: three of them ask for a pen (47, the dice, is filed
under trivia but lives here). `selection.ANALOG` caps the pen slots - 48, 50, 87
and 49 - at two a day: one is a good morning, three is a worksheet. They are
spread across the tiers, so nothing in the tier weights or the recency curve
correlates them and no other mechanism could see the collision coming.
*Sized on paper.* Four ruled lines at 44px - 30px was too tight to write on -
and four comic panels in a 2x2, since three across 72mm gives panels too small
to draw in.
*A layout described in a brief is part of the layout.* The panel count lives in
the narrator's instruction too ("four empty panels are printed beneath"); change
one without the other and the header announces the wrong number of frames.
The dice are seeded like everything else, so a reprint cannot re-roll them,
which is the entire point of a die. The journaling and comic prompts sit in
`body` where the narrator can voice them; the ruled lines and empty panels sit
in `fine`, which is never narrated and so cannot be overwritten with a sentence.

**49 · Big three checkboxes** — built · common · 42mm
Three bordered boxes and three ruled lines. Boxes are CSS borders rather than a
ballot-box glyph, which Special Elite does not have. The lines are 8mm apart,
which is school-ruled, and the box is 4mm.

**51 · Micro-dare** — built · uncommon · 20mm
Twenty dares, each doable today with no money, planning or anyone else's
agreement. Python picks which; the persona phrases it - a duty officer issuing
an order should not sound like a clerk proposing an amusement. Every persona
carries a `micro_dare` rename, and the fallback header is `Today's Mission`, so
the internal name never reaches paper even if the narrator fails.
**OPS never prints this as a section.** Its masthead files the day's orders, one
paragraph of which is the mission, and this slot would be the same instruction
a second time. OPS declares `[persona.absorbs] 51 = "mission"`, so on a day it
is drawn the dare is folded into that paragraph - written from this slot's own
text, set at the scale of a section - and no section is rendered (SYSTEM.md
3.8.1). The line still appears in the itemization and the recorded draw,
because it did print; it printed higher up.

**55 · Reversed-out black panel** — built · rare · 34mm
One sentence knocked out white on a solid black slab. Rare because a 30mm block
of solid ink is the most demanding thing this printer is asked to do. Styled by
`.slot-55` in the base template rather than in the slot, because the body has to
stay narratable — a slot that puts its own markup in `body` must be verbatim.
Bold and oversized, since reversed-out strokes lose weight to surrounding ink.
Prints with no header; the panel is the whole section.

**57 keep this one, 59 ruler down the edge** — live · rare · 0–18mm
Renderer slots. Neither has content in the ordinary sense; each is a property of
the physical object, which is why they are rare and why they are not narrated.
*The ruler is a real ruler, and that is checkable.* 576 dots across 72mm is
exactly 8 dots per millimetre, so a tick every 8 pixels is a millimetre with no
rounding anywhere along its length - 121 ticks, every gap exactly 8.0px, 960px
for the 120mm claimed, and it measures true against a tape on paper.
*It costs no paper because it draws outside its own box*, positioned absolutely
against `.receipt`. It insets the page **only on the days it draws**, from its
own stylesheet via `:has()`, rather than the base sheet carrying a permanent
gutter for a rare slot - invariant 3 says the page has no gutters of its own.
*Slot 53, fold-to-reveal, was built, printed and cut* - see the CUT table in
`SLOTS.md`.

---

## Trivia and numbers

**43 · Year-percent progress bar** — built · uncommon · 20mm
Fraction of the year elapsed, as a solid bar with month ticks. Ticks are drawn
white through the filled part and black through the empty part, because a
lighter ink over the top would be a grey and greys resolve to white at the page
threshold. The day itself counts as elapsed, so 31 December reads 100%.

**44 · Days alive** — built · uncommon · 22mm
Computed from the full date of birth (`QG_BIRTHDAY`), never stored, with the
next thousandth day and when it falls. Set large, because the count is the
section. No date of birth, no section.

**46 · Machine facts** — live · uncommon · 26mm
Every fact is computed at compose time from `printer.base`, the font manifest,
the registry and the store, so a fact cannot rot. Only the datasheet numbers are
hardcoded, and they are flagged in the module as the thing to re-check on any
printer swap. Never about how much paper is left.

---

## Legendary

**134 full persona takeover, 144 full short story** — built · legendary
One thing under two names: SLOTS.md lists them as slots, SYSTEM.md 4.1 as formats
8 and 9. They abandon the receipt, which a slot cannot do, so the work is in
`legendary.py`; `slots/legendary_slots.py` registers them for the catalogue and
never prints a section. The takeover sets the persona's own face with a headline
it writes and no spine at all. The story uses the corpus at SYSTEM.md 4.2's
weighting - 1,500-2,500 words nine times in ten, up to 6,000 the tenth - with a
one-line persona introduction and a drop cap, and never repeats a story.

**118 · One-day-only slots** — built · legendary · 40mm
Birthday, solstices and equinoxes, and 29 February. They **bypass the draw
entirely**: the section prints on the date and cannot print on any other.
*The astronomical dates are computed with PyEphem, not tabled* - they drift
across two calendar days year to year, and "21 June" is wrong often enough to
matter on the one day the section exists for. The local day is the machine's own
time zone's.
*Occasions can coincide, and the section is written for both* - a birthday on
an equinox is one section about both rather than two that ignore each other.
*The birthday is a full date*, `QG_BIRTHDAY` as DD-MM-YYYY in `.env` - day
first, and enforced rather than guessed, because 03-04 is a different birthday
under each convention and a wrong guess prints the section a month early. With
the year known, the section hands the narrator the exact age rather than letting
it infer one.

### Legendary formats (SYSTEM.md 4.1)

**A legendary day is a format, not a slot.** The formats are printer and
renderer behaviours a text model cannot improvise, with fresh content written
into them. Each format uses one or more of four hooks: `page()` replaces the
receipt, `css` restyles it, `transform()` changes the finished bitmap,
`variants()` prints more than one copy.

| # | Format | How |
|---|---|---|
| 1 | Prints twice | Second copy identical down to the serial, stamped CUSTOMER COPY |
| 2 | Breaks character | Persona dropped; the machine writes plainly to the reader, in mono |
| 5 | Blank but for one line | ~18cm of paper, one line dead centre |
| 6 | Fully reversed out | Inverted **after** the page threshold, not in CSS |
| 7 | Sign here | A signature line and nothing else |
| 8 | Full persona takeover | The persona's own face and headline, no spine (slot 134) |
| 9 | Full short story | A whole public-domain story, SYSTEM.md 4.2 weighting (slot 144) |
| 11 | Printed upside-down | Bitmap rotated, no acknowledgement |
| 12 | Corrupted print | Seeded bit-rot that worsens down the page |
| 13 | The torn receipt | Stops mid-line against a drawn ragged edge |
| 14 | One enormous QR | Full-width code of the day's sections, nothing else |
| 16 | A bill for what you did not get | Itemized undrawn slots, AMOUNT DUE |
| 20 | Mostly footnotes | One line of content, a page of qualifications |

*Reversed out is inverted after thresholding, deliberately.* Reversing the page
in CSS would antialias white glyphs against black and let the threshold eat
their strokes - the exact failure invariant 6 exists for. A 1-bit image inverted
after the threshold keeps every stroke exactly as wide as it was drawn.
*Upside-down rotates the bitmap* rather than using the printer's native mode,
which SYSTEM.md names. The physical result is identical, and nothing then depends
on the printer's own command set.
*Corruption is the damage a failing thermal printer really produces* - dropped
scanlines from a dead element band, rows smeared as the paper stalls, a column
of garbage from a stuck element - and it rises down the page, so it reads as a
machine deteriorating mid-print rather than a page broken from the start.
*The torn receipt* snaps its tear into the middle of a text line (never a rule
or header bar, which reads as layout).

**Formats draw without repeats until the pool is exhausted**, per the spec. The
used list lives in the store; a simulation or a `--legendary` preview draws from
it without consuming a format. **Every format falls back.** A missing narrator
gives curated copy, the format's own freeform call obeys `--offline` and
`--no-narrator`, and a format that raises leaves the ordinary receipt to print.
Two renderer affordances exist for them: `trim=False`, because "blank but for
one line, dead centre" has no centre once the renderer trims everything below
the line, and `strict_budget=False`, since their length is the design.
Double width (15) and addressed-to-someone-else (21) need `main.py` to hand a
format the receipt HTML before the first render.

`--legendary KEY` forces a format, or `--legendary any` draws one.

---

## Shared machinery

**Tier and paper size are config, not code.** A slot declares the tier the
catalogue gives it; `[slots.tier]` and `[slots.paper_mm]` in `config.toml`
override it at run time, and `[slots] disabled` retires one without deleting it.
`slot.base_spec` keeps the declared version so the coverage report can tell a
deliberate retuning apart from the code drifting from the docs.

**An embedded monospace on every page.** `--font-mono` is always available
whatever the persona face is. ASCII art, grids and anything aligned by column
need a fixed pitch, and falling back to whatever monospace the machine has makes
the render non-deterministic.

**HTTP and caching are shared.** `sources/http.py` carries the user agent, the
timeout and the last-known-good cache that every network source needs. It
returns `(payload, stale)` rather than just the payload, so a slot can say on
paper that it is serving yesterday's answer — reporting a cached answer as fresh
is the one failure worse than dropping the section.

**Persona renames are bound to their own section.** Each `[persona.vocabulary]`
entry reaches the narrator labelled with the section it belongs to, and the
prompt says a borrowed header puts the wrong title on the wrong content. An
unlabelled list of names gets one applied to the wrong section.

**An `after_narration` hook on the slot contract.** Called on real mornings only
with what the narrator actually wrote, so the few slots whose content only exists
once it is written - the search slots' fallbacks, the running bit - can keep it.
`ctx.shared["drawn_ids"]` is set before any slot runs, which the changelog and
tomorrow-predicted both need.

**QR codes are asserted, not eyeballed.** `tools/qrtest.py` renders a code
through a real page, thresholds it as the morning run would, samples it back to
one pixel per module and diffs it against the encoder's matrix. One real
interaction it guards: the renderer trims trailing white from the page, and **a
QR's bottom quiet zone is trailing white**, so a code with nothing under it would
lose four modules of margin and stop acquiring. Every real receipt has something
below a QR, but a slot that ever placed one last would hit it.

---

## Lessons from paper

**A paper estimate is a worst case, measured.** Budget fitting runs *before*
anything is fetched, so the spec is all the engine ever sees; an optimistic
figure gets a slot drawn onto a day it does not fit, and the render fails its
budget check at seven in the morning. `tools/papercheck.py` renders each slot
alone across a fortnight of dates and compares the worst case to the claim. Most
of a slot's cost is a fixed per-section overhead — header, rules, margins, and
for a puzzle its upside-down answer — which is why the smallest slots
under-report worst in proportion.

**The spine is reserved, not fitted.** It prints every day and is never drawn, so
`paper.spine_reserve_mm` comes off the budget before the engine fits anything,
and `render_within_budget()` catches an overflow anyway, dropping the largest
rotating slot and re-rendering. Invariant 1 says a dead source must never produce
a stack trace instead of a receipt; a fat one should not either.

**Synthesised bold is smear.** Several embedded faces (VT323 and Special Elite
among them) ship one weight, and a browser asked for 700 smears each glyph
sideways. `tools/boldtest.py` renders a sample at 400 and 700 through a real page
at the page threshold:

| | ink change | stroke change | `font-synthesis: none` |
|---|---|---|---|
| faces with a real bold | +31% to +66% | +31% to +77% | no effect |
| VT323 | +53% | +59% | **−35% ink** |
| Special Elite | +50% | +66% | **−33% ink** |

Turning synthesis off changes nothing for a face that has a real bold, and
removes a third of the ink from those that do not. On reversed-out text it is
worse than useless — the black smears *into* the white glyph and closes the
counters. Hence `font-synthesis: none` in the base stylesheet plus a `--bold`
token that resolves to 700 or 400 per face.

**Check a layout inside a real receipt.** Class names collide with the persona
themes (a generic `.bar` inherits a theme's black scoreboard), SVG `<pattern>`
ids collide between fragments on one page, and a CSS `\A` line break eats the
character after it. Each rendered perfectly on a page of its own.

**Verified on paper:** QR codes scan from thermal paper with a phone, the
dithered painting holds its gradations, and solid black rules directly above a
dithered block show no heat bleed.

---

## Section treatments

The text-only slots are all the same shape - a header, then a paragraph - and
eight of those in a row is a wall. Each family has its own typographic
behaviour, defined by slot id in the base stylesheet so a theme can still
override any of it.

Three constraints shape all of them, and are why none of it looks like ordinary
web design:

- **No greys, no opacity**, so hierarchy comes from size, rules, boxes and
  reversed-out ink. There are no soft tints to lean on.
- **`--bold` is 400 on several faces**, so weight cannot carry emphasis by
  itself. Every treatment works with no weight change at all and takes bold as a
  bonus where the face has one.
- **The narrator rewrites most of these bodies**, so nothing can depend on
  markup inside them. Each rule works on a plain run of prose - `::first-letter`,
  borders, `::before` marks - plus the `fine` line, which is never narrated.

| Treatment | Slots | What it does |
|---|---|---|
| Pull quote | 143, 98, 25 | Rules above and below, attribution hung right. Rules rather than quotation marks: every face has a rule, and VT323's quotes are two square pixels. |
| Dictionary entry | 31, 32, 147 | A drop cap - the one piece of hierarchy needing neither weight nor colour, and at three lines it is a shape rather than a letter, which is what survives a threshold. |
| Citation rule | 32 | A rule down the left. The other half of keeping the true etymology distinguishable from the invented word, which has the dagger. |
| Spec plate | 46 | Two corner brackets and fixed pitch. A full border would make it another box; brackets read as a machine plate. |
| Hazard plate | 33 | Double rule above and below. Says "read this one" without a heavier weight. |
| Cartouche | 150 | Double-ruled box, centred letterspaced name, the invention disclosure set into its foot so it reads as part of the frame rather than an apology. |
| Given room | 149 | Deliberately the least decorated section on the page. A joke in a box is a joke being introduced, and a joke being introduced has already failed. |
| Filed | 130, 138 | Rules down both sides, so a fact reads as retrieved rather than asserted. |
| Hanging indent | 111, 115 | Reads as a quoted argument rather than the receipt's own opinion, which matters most on the steelman. |
| Reversed out | 51 | An instruction should look like one. The black panel's logic at one line. |

---

## Decisions and open questions

**The narrator stays loose.** It has been caught adding a fact that was not in
its brief — crediting Poisson alongside Navier and Stokes on the most-read slot.
The fact is correct, and house rule one says a figure not in the brief does not
reach the paper. The call was to keep that latitude: a stricter narrator makes
every slot flatter. The rule stands for *figures* — weather numbers, prices,
quotations, ranks — and the latitude is for colour around them.

**Micro-print (58) breaks the type floor deliberately.** It is specified as
legible only through a phone camera, which means going below 12px — the one
measured invariant in `CLAUDE.md` with no exceptions. It needs an explicit
carve-out before it is built, not a quiet override.
