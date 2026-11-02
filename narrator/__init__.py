"""The narrator - one Claude call per receipt, per SYSTEM.md section 10.

It receives the facts and returns the voice. It never invents a fact, and the
schema is built so that it *cannot* rewrite the things that must survive
verbatim.

Three design decisions worth knowing before changing anything here.

**The schema is built at run time, not declared.** Which slots ran is a property
of the day, so a static Pydantic model cannot describe the response. The JSON
schema is assembled from the drawn slots each morning.

**Verbatim slots get no body field at all.** News headlines and quotations must
reach paper unaltered (SYSTEM.md section 9). Rather than instructing the model
not to rewrite them and hoping, those slots are given only a `header` property in
the schema - there is no field in which a rewrite could arrive. Structural
enforcement beats a politely worded rule.

**A failed generation is not an error.** Every slot already carries templated
copy that prints perfectly well. If the call fails, the response fails schema
validation, or the API is unreachable, the receipt prints in the slot's own words
and nobody's morning is ruined. A flat receipt is fine; a broken one is not.

Prompt caching is deliberately absent: this runs once every 24 hours, so every
call starts cold and there is no warm cache to design around.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date as Date
from typing import Any

import config

log = logging.getLogger(__name__)

# One model, every morning. A stronger model on rare days cost several times as
# much - and stacked with web search, whose results are billed as input - for
# prose nobody could pick out of a line-up on paper.
MODEL = "claude-sonnet-5"
# Input and output price per million tokens, for the cost line on the console.
PRICE_PER_MTOK = (2.0, 10.0)

# Room to think, search, and then still write. A cap is not a budget: only what
# is generated is billed, and the reply itself is under a thousand tokens. What
# the cap actually does is decide whether the answer exists at all - at 8000, a
# morning with two web searches can spend the lot on thinking and search
# results and stop at max_tokens with no text block in the response, which
# fails silently and prints templated copy. The headline picker below has the
# same note for the same reason.
MAX_TOKENS = 16000
RECEIPTS_BEFORE_CONTINUITY = 14

# Anthropic's server-side web search. Declared on the request, run on their
# infrastructure, results returned as content blocks in the same response - so
# a search slot costs no extra round trip and the narrator stays one call
# (SYSTEM.md 10.2). Search composes with a strict output schema
# (`output_config.format`).
SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}
# Enough to answer two or three slots properly, few enough that a model which
# decides to go exploring cannot run the morning's bill up.
MAX_SEARCHES = 8
# Anthropic charges per search on top of tokens.
SEARCH_USD = 0.01


@dataclass
class Narration:
    """What the narrator produced. Every field is optional by design."""

    headers: dict[int, str] = field(default_factory=dict)
    bodies: dict[int, str] = field(default_factory=dict)
    fines: dict[int, str] = field(default_factory=dict)
    continuity: str | None = None
    # The persona's own masthead lines ([persona.masthead]), by key.
    masthead: dict[str, str] = field(default_factory=dict)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0
    search_failed: bool = False

    @property
    def cost_usd(self) -> float:
        rate_in, rate_out = PRICE_PER_MTOK
        tokens = (self.input_tokens * rate_in + self.output_tokens * rate_out) / 1e6
        return tokens + self.searches * SEARCH_USD


def _is_verbatim(brief: dict) -> bool:
    """Slots whose body must reach paper unaltered."""
    return bool(brief.get("verbatim"))


# A masthead line longer than its field's `max_chars` (this, by default) is cut
# at a word. The theme sets these in a fixed space, and a model asked for "two to
# five words" occasionally delivers a sentence.
MASTHEAD_MAX_CHARS = 90


def build_schema(narrated: list[dict], continuity: bool,
                 masthead: dict | None = None) -> dict:
    """A JSON schema describing exactly today's receipt.

    Every narrated slot gets a `header`. Only non-verbatim slots get a `body`,
    which is how "do not rewrite the headlines" is enforced. A persona that
    declares `[persona.masthead]` fields gets a `masthead` object with exactly
    those, each described by its own instruction.
    """
    slot_props: dict[str, Any] = {}
    for item in narrated:
        props: dict[str, Any] = {
            "header": {
                "type": "string",
                "description": "This section's title, renamed into the persona's "
                               "own vocabulary. Never the internal slot name.",
            }
        }
        required = ["header"]
        if not _is_verbatim(item["brief"]):
            props["body"] = {
                "type": "string",
                "description": item["brief"].get(
                    "instruction", "Write this section in voice."),
            }
            required.append("body")
        # A slot whose small print belongs to the persona (the coupon) asks for
        # it by describing it; without this its `fine` stays the slot's own.
        if fine := item["brief"].get("fine_print"):
            props["fine"] = {"type": "string", "description": fine}
            required.append("fine")
        slot_props[str(item["id"])] = {
            "type": "object", "properties": props,
            "required": required, "additionalProperties": False,
        }

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "slots": {
                "type": "object", "properties": slot_props,
                "required": list(slot_props), "additionalProperties": False,
            }
        },
        "required": ["slots"],
        "additionalProperties": False,
    }
    if masthead:
        schema["properties"]["masthead"] = {
            "type": "object",
            "properties": {
                key: {"type": "string",
                      "description": spec.get("instruction", "Write this in voice.")}
                for key, spec in masthead.items()
            },
            "required": list(masthead),
            "additionalProperties": False,
        }
        schema["required"].append("masthead")
    if continuity:
        schema["properties"]["continuity"] = {
            "type": "string",
            "description": "One sentence in which today's persona refers to a "
                           "recent one. Grudges and running complaints welcome. "
                           "Empty string for none.",
        }
        schema["required"].append("continuity")
    return schema


def system_prompt(persona: dict) -> str:
    vocab = persona.get("vocabulary", {})
    # Labelled by the section each belongs to. An unlabelled list of renames
    # gets one applied to the wrong section - a joke printed under TODAY'S
    # MISSION, which is the micro-dare's name.
    renames = "\n".join(f"  - the {k.replace('_', ' ')} section: {v}"
                        for k, v in vocab.items())
    return f"""You write one morning receipt, printed on a thermal till roll and
read standing up. You are today's persona and you do not break character.

PERSONA: {persona.get('display', persona['name'])}
{persona.get('voice', '').strip()}

Section headers this persona has already settled on. Each belongs to ONE named
section and is not available to any other - a header borrowed from a different
section puts the wrong title on the wrong content:
{renames or '  (none given - invent them in voice)'}

Every other section needs a header invented in the same spirit.

HOUSE RULES, in order of importance:

1. Never invent a fact. Weather figures, sky data, quotations, headlines and
   prices are supplied to you and are true. Write around them, never past them.
   If a figure is not in your brief, it does not go on the receipt.
2. Every section header is renamed into your vocabulary. An internal name like
   "Weather verdict" or "Micro-dare" must never reach paper.
3. Write for 72mm of paper. One or two sentences per section. This is glanced
   at over breakfast, not read in a chair.
4. Follow each slot's own instruction - it says what that section needs.
5. No markdown, no emoji, no headings inside a body. Plain sentences.
6. Fabrication that is meant to be fabricated - invented words, conspiracies -
   is fine where a slot asks for it, and is marked as such by the layout. Do not
   smuggle invention into a factual section.
7. The weather has its own section; leave it there. When a header, a masthead
   line, the small print or any other section calls back to something on
   today's receipt, reach for the rest of the page first - a headline, the
   puzzle, the quote, the joke, the day of the week, whatever is strangest
   today. Outside the weather section, the weather is mentioned at most once
   on the whole receipt, and never as the easy default. The persona's example
   lines show its register, not its subject matter.
"""


def _digest(receipts: list[dict]) -> str:
    if not receipts:
        return "This is the first receipt. There is no past to refer to."
    lines = []
    for r in receipts:
        slots = ", ".join(str(s) for s in r.get("slots", [])[:6])
        lines.append(f"  {r['day']}  no.{r['number']}  {r['persona']}  [{slots}]")
    return "Recent receipts, newest first:\n" + "\n".join(lines)


def build_user_content(day: Date, persona: dict, narrated: list[dict],
                       receipts: list[dict]) -> str:
    payload = {
        "date": day.isoformat(),
        "weekday": f"{day:%A}",
        "sections": [
            {
                "id": item["id"],
                "name": item["name"],
                "current_text": item.get("current"),
                "facts": {k: v for k, v in item["brief"].items()
                          if k not in ("instruction", "verbatim",
                                       "fine_print")},
                "instruction": item["brief"].get("instruction",
                                                 "Write this in voice."),
                "verbatim": _is_verbatim(item["brief"]),
                "search_the_web_for_this": bool(item.get("needs_search")),
            }
            for item in narrated
        ],
    }
    return (f"{_digest(receipts)}\n\nToday's receipt:\n"
            f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
            "Write each section. Sections marked verbatim keep their existing "
            "text unchanged - give those a header only."
            + ("\n\nThe masthead fields are this persona's own furniture at the "
               "top of the page. They are fiction and are never a fact: no real "
               "people, places in the news, or headlines, and none of today's "
               "real figures. Something new every day."
               if persona.get("masthead") else ""))


def _client():
    """An Anthropic client, or None when there is no key or no SDK.

    An API key that is not scoped to a workspace needs the workspace named
    explicitly: either use a workspace-scoped key or set ANTHROPIC_WORKSPACE_ID
    in .env - the API says which, and the message is surfaced on failure.
    """
    config.load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        headers = {"anthropic-workspace-id": workspace} if workspace else None
        return anthropic.Anthropic(default_headers=headers)
    except Exception:  # noqa: BLE001 - no SDK, or no client: templated copy
        return None


def wants_search(narrated: list[dict]) -> bool:
    return any(item.get("needs_search") for item in narrated)


def write(day: Date, persona: dict, narrated: list[dict],
          receipts: list[dict] | None = None) -> Narration | None:
    """One call. Returns None on any failure - the caller falls back."""
    if not narrated:
        return None
    client = _client()
    if client is None:
        log.info("no ANTHROPIC_API_KEY or anthropic SDK; using templated copy")
        return None
    import anthropic

    receipts = receipts or []
    continuity = len(receipts) >= RECEIPTS_BEFORE_CONTINUITY

    # Search is attached only when a drawn slot actually needs it. Declaring it
    # unconditionally would invite the model to go looking on days when every
    # fact it needs is already in the brief, which is both slower and a way to
    # smuggle unverified detail onto a factual receipt.
    extra: dict[str, Any] = {}
    if wants_search(narrated):
        extra["tools"] = [dict(SEARCH_TOOL, max_uses=MAX_SEARCHES)]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt(persona),
            messages=[{"role": "user",
                       "content": build_user_content(day, persona, narrated,
                                                     receipts)}],
            output_config={"format": {"type": "json_schema",
                                      "schema": build_schema(
                                          narrated, continuity,
                                          persona.get("masthead"))}},
            **extra,
        )
    except anthropic.AuthenticationError:
        log.warning("ANTHROPIC_API_KEY rejected; using templated copy")
        return None
    except anthropic.RateLimitError:
        log.warning("rate limited; using templated copy")
        return None
    except anthropic.APIStatusError as exc:
        # Surface the message, not just the code: a bare "API error 400" looks
        # like a schema fault and is as likely to be a missing workspace header.
        detail = ""
        try:
            detail = (exc.body or {}).get("error", {}).get("message", "")
        except AttributeError:
            detail = str(exc)
        log.warning("narrator API error %s: %s; using templated copy",
                    exc.status_code, detail)
        return None
    except anthropic.APIConnectionError:
        log.warning("narrator unreachable; using templated copy")
        return None

    # A refusal is a valid HTTP 200, so stop_reason is checked before content.
    if response.stop_reason == "refusal":
        log.warning("narrator refused; using templated copy")
        return None

    try:
        # The LAST text block, not the first. With server-side search attached,
        # the reply is a sequence - search calls, results, the model's own
        # commentary - and the structured answer is what it ends on. Taking the
        # first text block gets a sentence about what it is about to look up.
        text = next(b.text for b in reversed(response.content) if b.type == "text")
        data = json.loads(text)
    except (StopIteration, json.JSONDecodeError):
        # Say which of the two it was. A truncated reply and a reply that was
        # never JSON look identical from the receipt's side and are fixed in
        # completely different places.
        blocks = ", ".join(b.type for b in response.content) or "none"
        log.warning("narrator returned no parsable JSON (stop_reason=%s, "
                    "blocks: %s); using templated copy",
                    response.stop_reason, blocks)
        return None

    out = Narration(model=MODEL,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens)

    # Server-tool failures do not raise (SYSTEM.md 10.2) - an error arrives as a
    # result block carrying an error payload. Counted rather than acted on: the
    # response is still valid JSON, the affected slot simply has thinner facts,
    # and it is the slot's cached fallback that decides what to do about it.
    for block in response.content:
        if "search_tool_result" in getattr(block, "type", ""):
            out.searches += 1
            content = getattr(block, "content", None)
            if getattr(content, "type", "") == "web_search_tool_result_error":
                out.search_failed = True
    for raw_id, section in (data.get("slots") or {}).items():
        try:
            sid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if header := (section.get("header") or "").strip():
            out.headers[sid] = header
        if body := (section.get("body") or "").strip():
            out.bodies[sid] = body
        # Kept even when empty: an empty string is the narrator saying this
        # form has no fine print, and the offline terms must not print under it.
        if "fine" in section:
            out.fines[sid] = " ".join(str(section.get("fine") or "").split())
    out.continuity = (data.get("continuity") or "").strip() or None
    for key, spec in (persona.get("masthead") or {}).items():
        text = " ".join(str((data.get("masthead") or {}).get(key) or "").split())
        limit = int(spec.get("max_chars", MASTHEAD_MAX_CHARS))
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-") + "..."
        if text:
            out.masthead[key] = text
    return out


def freeform(day: Date, persona: dict | None, instruction: str,
             max_words: int = 120) -> str | None:
    """One short piece of writing for a legendary format. None on any failure.

    The ordinary call writes into the day's slots. A legendary format that
    replaces the whole page has no slots to write into - "blank but for one
    line", "breaks character" - so it gets its own small call instead. About
    fifteen a year, so the cost is a rounding error.

    `persona` may be None, which is the point for formats where every persona
    drops away and only the machine is left talking.
    """
    client = _client()
    if client is None:
        return None
    voice = (system_prompt(persona) if persona else
             "You write one short piece for a thermal receipt printer that "
             "prints a brief every morning. Today there is no persona. Write "
             "plainly, in the first person, as the machine itself. Never invent "
             "a fact about the world.")
    schema = {"type": "object",
              "properties": {"text": {"type": "string",
                                      "description": instruction}},
              "required": ["text"], "additionalProperties": False}
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=1024, system=voice,
            messages=[{"role": "user",
                       "content": f"Date: {day:%A %d %B %Y}.\n\n{instruction}\n\n"
                                  f"At most {max_words} words."}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason == "refusal":
            return None
        text = next(b.text for b in response.content if b.type == "text")
        return (json.loads(text).get("text") or "").strip() or None
    except Exception as exc:  # noqa: BLE001 - a legendary day falls back, never crashes
        log.warning("freeform narrator failed: %s", exc)
        return None


def design(day: Date, persona: dict, brief: str,
           max_tokens: int = 8000) -> dict | None:
    """A small printed object designed from scratch in the persona's voice.

    Slot 151. Unlike the other calls this one returns markup, not sentences:
    the persona writes AND lays out a ticket, a flyer, a dog tag. It gets the
    printer's physical limits as instructions and nothing else - if it ignores
    them the section prints badly or drops, which is a bad morning, not a
    broken machine. Returns {"title", "html"} or None on any failure.
    """
    client = _client()
    if client is None:
        return None
    voice = (f"You are {persona.get('display', persona['name'])}, and today you "
             f"design and write one small printed object that comes out of a "
             f"thermal receipt printer as part of {config.reader_name()}'s "
             f"morning receipt.\n\n"
             f"{persona.get('voice', '').strip()}\n\n"
             f"Stay completely in character, in the words AND in the design. "
             f"Never invent a fact about the real world that could be mistaken "
             f"for true; the object itself is openly invented.")
    schema = {"type": "object",
              "properties": {
                  "title": {"type": "string",
                            "description": "Section header, in voice, a few words."},
                  "html": {"type": "string",
                           "description": "The object: HTML with one <style> block."}},
              "required": ["title", "html"], "additionalProperties": False}
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=max_tokens, system=voice,
            messages=[{"role": "user",
                       "content": f"Date: {day:%A %d %B %Y}.\n\n{brief}"}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return None
        text = next(b.text for b in response.content if b.type == "text")
        out = json.loads(text)
        if not (out.get("html") or "").strip():
            return None
        return out
    except Exception as exc:  # noqa: BLE001 - the section drops, nothing else
        log.warning("design narrator failed: %s", exc)
        return None


@dataclass
class Pick:
    """One headline the ranker chose: its index, the line under it, and - when
    it continues a story already printed this week - which one."""
    index: int
    gloss: str = ""
    follows: int | None = None


def _usage(label: str, response: Any) -> None:
    u = getattr(response, "usage", None)
    if u is not None:
        log.info("%s: %s in / %s out tokens", label,
                 getattr(u, "input_tokens", "?"), getattr(u, "output_tokens", "?"))


def rank(day: Date, taste: str, headlines: list[dict], count: int,
         previously: list[dict] | None = None,
         grim_max: int = 2) -> list[Pick] | None:
    """Pick `count` headlines for slot 10 by reading the profile as prose.

    The offline ranker is keyword overlap, and prose defeats it: "acquisitions,
    unless the thing acquired is interesting on its own" puts *interesting* in
    the anti-list. This call reads the same file the way it was written to be
    read. Returns picks, best first, or None on any failure - the caller falls
    back to the keyword ranking, which is not a bad morning, only a blunter one.

    The gloss is one short line printed under a headline that does not stand on
    its own. It comes from that item's own summary, which is supplied here, and
    is never invented: a receipt that explains a headline wrongly is worse than
    one that leaves it cryptic.

    `previously` is what printed in the last few days, as {"title", "when"}.
    It costs a few hundred tokens and buys two things: the same story under a
    new headline is not picked again, and a genuine development is marked as a
    follow-up of the day it first printed.

    **Cheap on purpose.** It runs every morning, so it runs at low effort: a
    ranking is a judgement of taste, not a proof, and thinking was most of what
    this call cost. The caller trims every summary before it gets here.
    """
    client = _client()
    if not (taste.strip() and headlines and client):
        return None

    listing = "\n".join(
        f"{n}. [{h['source']}] {h['title']}"
        + (f"\n     summary: {h['summary']}" if h.get("summary") else "")
        for n, h in enumerate(headlines))
    earlier = ""
    if previously:
        earlier = ("\n\nALREADY PRINTED IN THE LAST FEW DAYS:\n" + "\n".join(
            f"P{n}. ({p['when']}) {p['title']}"
            for n, p in enumerate(previously)))
    schema = {"type": "object",
              "properties": {"picks": {
                  "type": "array",
                  "items": {"type": "object",
                            "properties": {"index": {"type": "integer"},
                                           "gloss": {"type": "string"},
                                           "follows": {"type": "integer"}},
                            "required": ["index", "gloss", "follows"],
                            "additionalProperties": False},
                  "description": f"The {count} best headlines, best first."}},
              "required": ["picks"], "additionalProperties": False}
    try:
        response = client.messages.create(
            # Room for the model to think first: a tight cap truncates the
            # response before the text block exists at all, which failed
            # silently every busy morning - a thinking block and nothing else.
            model=MODEL, max_tokens=2048,
            system="You choose which headlines are worth one strip of paper on "
                   "someone's breakfast table. You are given their own account "
                   "of what they care about, written as prose - read it as "
                   "prose, including its qualifications and its tone. You only "
                   "select; you never rewrite a headline.",
            messages=[{"role": "user",
                       "content": f"THEIR TASTE, IN THEIR WORDS:\n{taste}\n\n"
                                  f"TODAY'S CANDIDATES:\n{listing}{earlier}\n\n"
                                  f"Choose the {count} best for this reader, "
                                  f"best first. Prefer the specific over the "
                                  f"sweeping - one strange object beats a trend "
                                  f"piece. Spread them across outlets and "
                                  f"subjects. This is the whole of their news "
                                  f"for the day, so do not shy away from "
                                  f"serious news: unless nothing today is "
                                  f"genuinely important, one pick is the most "
                                  f"important world, French or Paris story on "
                                  f"the list - the one they would be "
                                  f"embarrassed not to know about by lunch - "
                                  f"even when it is grim. At most "
                                  f"{grim_max} bleak or violent, so the section "
                                  f"is never all bad news. Headlines in French "
                                  f"are fine.\n\n"
                                  f"Never pick a story that was already printed "
                                  f"(the P list), even under a different "
                                  f"headline - UNLESS something genuinely new "
                                  f"has happened in it. Then `follows` is that "
                                  f"P number; otherwise `follows` is -1.\n\n"
                                  f"For each pick also give `gloss`: ONE short "
                                  f"line, under 90 characters, that adds what "
                                  f"the headline leaves out - who or what "
                                  f"someone is, what the thing actually does, "
                                  f"the number, the cause, the consequence, the "
                                  f"detail that makes the story make sense. "
                                  f"Write one by default; return an empty "
                                  f"string ONLY when the headline is genuinely "
                                  f"self-contained or the summary adds nothing. "
                                  f"Write it in English.\n"
                                  f"Where the summary is a Hacker News top "
                                  f"comment, the gloss may quote a few of its "
                                  f"words in quotation marks as the top "
                                  f"comment's - snark included, attributed, "
                                  f"never passed off as the article.\n"
                                  f"Two hard rules: never restate the headline "
                                  f"in other words - if your line says the same "
                                  f"thing again it is worse than nothing - and "
                                  f"take every fact from that item's own "
                                  f"summary, inventing NOTHING."}],
            output_config={"format": {"type": "json_schema", "schema": schema},
                           "effort": "low"},
        )
        _usage("news ranking", response)
        text = next((b.text for b in response.content if b.type == "text"), "")
        if response.stop_reason in ("refusal", "max_tokens") or not text:
            log.warning("news ranking unusable: stop=%s", response.stop_reason)
            return None
        out: list[Pick] = []
        for pick in json.loads(text).get("picks", []):
            index = pick.get("index")
            if not (isinstance(index, int) and 0 <= index < len(headlines)):
                continue
            follows = pick.get("follows")
            if not (isinstance(follows, int) and previously
                    and 0 <= follows < len(previously)):
                follows = None
            out.append(Pick(index,
                            " ".join(str(pick.get("gloss") or "").split()),
                            follows))
        return out or None
    except Exception as exc:  # noqa: BLE001 - the keyword ranker covers it
        log.warning("news ranking failed: %s", exc)
        return None


# The cheap model, for judgements small enough not to need the narrator's:
# whether three headlines are worth a slot (115). Twenty times cheaper per token.
CHEAP_MODEL = "claude-haiku-5-5"


@dataclass
class Framing:
    """Slot 115's verdict: which group, which three headlines, and in a line,
    what actually differs between them - handed to the narrator as a fact."""
    group: int
    picks: list[int]
    angle: str


def framings(groups: list[list[dict]]) -> Framing | None:
    """Slot 115: is any story told three genuinely different ways today?

    Python has already grouped today's headlines by shared vocabulary, which is
    free and finds the stories several outlets covered. What it cannot tell is
    "the same event, framed differently" - the whole point - from "the same
    topic, a different article", nor whether the difference is worth a slot.
    This call makes both judgements, on the cheap model at low effort, over a
    few dozen headlines. It is also the gate: None means nothing qualified (or
    the call failed), and the slot does not print.
    """
    client = _client()
    if not (groups and client):
        return None
    listing = "\n\n".join(
        f"GROUP {g}:\n" + "\n".join(
            f"  {n}. [{h['source']}] {h['title']}" for n, h in enumerate(group))
        for g, group in enumerate(groups))
    schema = {"type": "object",
              "properties": {"interesting": {"type": "boolean"},
                             "group": {"type": "integer"},
                             "picks": {"type": "array",
                                       "items": {"type": "integer"}},
                             "angle": {"type": "string"}},
              "required": ["interesting", "group", "picks", "angle"],
              "additionalProperties": False}
    try:
        response = client.messages.create(
            model=CHEAP_MODEL, max_tokens=2048,
            system="You compare how news outlets frame the same event. You "
                   "only select and judge; you never rewrite a headline.",
            messages=[{"role": "user", "content":
                f"{listing}\n\nEach group is headlines that share vocabulary "
                f"and MAY be about one news event. Find the group where three "
                f"outlets frame the SAME specific event most differently - a "
                f"different emphasis, a different number, a different actor "
                f"made the subject, blame placed differently, a question "
                f"against a statement, a different consequence led with - and "
                f"pick those three headlines, from three different outlets, "
                f"preferring outlets from different countries or leanings.\n"
                f"All three must be about the same specific event, not merely "
                f"the same topic: an explainer, an opinion piece or a "
                f"neighbouring story does not count.\n"
                f"Then judge it honestly: `interesting` is true only if a "
                f"reader comparing the three would notice a real difference in "
                f"how the event is being told. Three wordings of the same "
                f"facts are NOT interesting. Most days nothing qualifies, and "
                f"false is the right answer then.\n"
                f"`angle`: one short sentence on what differs between the "
                f"three, from the headlines alone. Empty if not interesting."}],
            output_config={"format": {"type": "json_schema", "schema": schema},
                           "effort": "low"},
        )
        _usage("framings", response)
        text = next((b.text for b in response.content if b.type == "text"), "")
        if response.stop_reason in ("refusal", "max_tokens") or not text:
            return None
        data = json.loads(text)
        if not data.get("interesting"):
            return None
        g, picks = data.get("group"), data.get("picks") or []
        if not (isinstance(g, int) and 0 <= g < len(groups)):
            return None
        picks = [p for p in dict.fromkeys(picks)
                 if isinstance(p, int) and 0 <= p < len(groups[g])][:3]
        if len({groups[g][p]["source"] for p in picks}) < 3:
            return None
        return Framing(g, picks, " ".join(str(data.get("angle") or "").split()))
    except Exception as exc:  # noqa: BLE001 - no verdict is a dropped slot
        log.warning("framings failed: %s", exc)
        return None
