"""Slots 67, 69 and 22 - what the mailbox delivers.

The three slots whose content is written by a person rather than by the machine:
a line from a friend (67), a note from 11pm-you (69), and a letter to your
future self (22), which is written now and delivered months later.

**An email address is the entire interface.** Nothing to host, nothing to log
into. Friends are given the address; everything else arrives through a QR on
the receipt with the subject already filled in.

**The words are theirs.** A line from a friend prints verbatim, and so does a
letter from the reader's younger self. The persona names the section and may say
one thing around it, exactly as it does around a quotation - see the verbatim
rule, `CLAUDE.md` invariant 9. A persona rewriting a friend's message in voice would
be the worst failure available to this slot.

**Nothing is delivered twice.** The mailbox is never modified; each slot records
the message id it printed, so tomorrow moves on to the next one.
"""

from __future__ import annotations

import config
from sources import mailbox

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# How long a letter to your future self sits before it can be delivered. Long
# enough that it arrives as a surprise from someone you have stopped being.
LETTER_DELAY_DAYS = 90

_CSS = """
<style>
.mail-body { white-space: pre-wrap; }
.mail-from { font-size: var(--size-tiny); letter-spacing: .1em;
             text-transform: uppercase; margin-bottom: 5px; }
.mail-quote { border-left: 4px solid #000; padding-left: 12px; }
.qr-block { text-align: center; margin: 8px 0 2px; }
.qr-block img { margin: 0 auto; }
.qr-cap { font-size: var(--size-tiny); line-height: 1.3; margin-top: 4px; }
</style>
"""


def qr_block(subject: str, caption: str, body: str = "") -> str:
    """A scannable reply: the mailbox, pre-addressed and pre-titled."""
    from render.dither import img_tag
    from render.qr import mailto, qr_image
    payload = mailto(mailbox.address(), subject, body)
    return (f'<div class="qr-block">{img_tag(qr_image(payload))}'
            f'<div class="qr-cap">{caption}</div></div>')


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _first_name(sender: str) -> str:
    return (sender.split()[0] if sender.split() else sender).strip(",")


@register
class LineFromFriend(Slot):
    """67 - a friend emailed the mailbox, and their line prints."""

    spec = SlotSpec(id=67, name="A line from a friend", tier="uncommon",
                    paper_mm=26, needs_network=True, needs_narrator=True)

    def fetch(self, ctx: Context) -> SlotResult | None:
        waiting = mailbox.unused(ctx, "FRIEND")
        if not waiting:
            return None                       # nobody wrote; the section drops
        note = waiting[-1]                    # oldest first, so none is stranded
        mailbox.mark_used(ctx, note.uid)
        name = _first_name(note.sender)
        return SlotResult(
            head="From A Friend",
            body=(f'{_CSS}<div class="mail-from">{_escape(name)} wrote</div>'
                  f'<div class="mail-body mail-quote">{_escape(note.body)}</div>'),
            fine=f"Sent {note.sent:%d %B}." if note.sent else None,
            brief={"verbatim": True, "from": name,
                   "instruction": "Name this section in voice. A friend sent "
                                  "this line to the machine's mailbox and it "
                                  "prints exactly as written - do not rewrite, "
                                  "summarise or reply to it."},
        )

    def fixture(self, ctx: Context) -> SlotResult | None:
        return None                           # no mail offline, no section


@register
class NoteFromLastNight(Slot):
    """69 - written at eleven at night, delivered at breakfast."""

    spec = SlotSpec(id=69, name="Note from 11pm-you", tier="uncommon",
                    paper_mm=26, needs_network=True, needs_narrator=True)

    def fetch(self, ctx: Context) -> SlotResult | None:
        waiting = mailbox.unused(ctx, "TONIGHT")
        if not waiting:
            return None
        note = waiting[-1]
        mailbox.mark_used(ctx, note.uid)
        when = f"{note.sent:%A} night" if note.sent else "last night"
        return SlotResult(
            head="From Last Night",
            body=(f'{_CSS}<div class="mail-from">you, {_escape(when)}</div>'
                  f'<div class="mail-body mail-quote">{_escape(note.body)}</div>'),
            brief={"verbatim": True,
                   "instruction": "Name this section in voice. "
                                  f"{config.reader_name()} wrote this late at "
                                  "night, for the morning, and it prints "
                                  "exactly as written. You may remark on the "
                                  "hour it was sent, never on what it says."},
        )

    def fixture(self, ctx: Context) -> SlotResult | None:
        return None


@register
class LetterToFutureSelf(Slot):
    """22 - written whenever the mood strikes, printed back months later.

    Two states in one slot, which is the point of it: until a letter is old
    enough there is nothing to deliver, so the section prints the invitation
    instead - a QR that opens a blank email with LETTER in the subject. The
    delivery is the same slot keeping its promise.
    """

    spec = SlotSpec(id=22, name="Letter to your future self QR", tier="uncommon",
                    paper_mm=40, needs_network=True, needs_narrator=True)

    def _deliver(self, ctx: Context, note: mailbox.Message) -> SlotResult:
        mailbox.mark_used(ctx, note.uid)
        months = max(1, note.age_days // 30)
        ago = f"{months} month{'s' if months != 1 else ''} ago"
        return SlotResult(
            head="Delivery",
            body=(f'{_CSS}<div class="mail-from">you, {_escape(ago)}</div>'
                  f'<div class="mail-body mail-quote">{_escape(note.body)}</div>'),
            fine=f"Written {note.sent:%d %B %Y}." if note.sent else None,
            brief={"verbatim": True, "written_days_ago": note.age_days,
                   "instruction": "Name this section in voice. "
                                  f"{config.reader_name()} wrote this letter to "
                                  "a future self months ago and it "
                                  "prints exactly as written. You are the "
                                  "courier, not the author: you may say the "
                                  "letter has come due, nothing about its "
                                  "contents."},
        )

    def _invite(self, ctx: Context) -> SlotResult:
        return SlotResult(
            head="To Your Future Self",
            body=(f'{_CSS}'
                  + qr_block("LETTER",
                             "Write anything. It is kept, unread, and printed "
                             f"back no sooner than {LETTER_DELAY_DAYS} days "
                             "from now.")),
            brief={"verbatim": True,
                   "instruction": "Name this section in voice and add at most "
                                  "one short line inviting "
                                  f"{config.reader_name()} to write to a "
                                  "future self. The code and its caption print "
                                  "as they are."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        due = [m for m in mailbox.unused(ctx, "LETTER")
               if m.age_days >= LETTER_DELAY_DAYS]
        if due:
            return self._deliver(ctx, due[-1])
        if not mailbox.configured():
            return None                       # no mailbox, no address to print
        return self._invite(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._invite(ctx) if mailbox.configured() else None
