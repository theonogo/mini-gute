"""The input channel - one mailbox, read over IMAP, routed by subject.

SYSTEM.md 6. Everything inbound arrives as email to a dedicated account: no
hosting, no web endpoint, no OAuth, nothing to keep running. The QR slots print
`mailto:` links with the subject already filled in, so a reply costs a tap and a
sentence.

| Subject prefix | Feeds |
|---|---|
| FEEDBACK | prompted feedback (12) |
| LETTER   | letter to your future self (22) |
| PHOTO    | photo assignment and dead drop (66, 73) |
| FRIEND   | a line from a friend (67) |
| TONIGHT  | note from 11pm-you (69) |
| IDEA     | verdict on a proposed slot (141) |

**Read-only, and it never consumes twice.** Nothing is deleted, moved or marked
read on the server - the mailbox is a log, and a slot that failed to print
should be able to print tomorrow. Instead every message id that has been *used*
is recorded in the store by the slot that used it, so the same letter is not
delivered twice.

**One connection a morning.** The first slot to ask pays for the fetch and the
result is cached in `ctx.shared`; the rest read that. A mailbox that cannot be
reached returns nothing at all, and the slots that depend on it simply drop -
the morning is shorter, never broken.

**Attachments are photographs.** A PHOTO reply carries an image, which is saved
under `paths.photos` to resurface later as a printed photo, so the machine feeds
itself. Nothing else is written to disk.
"""

from __future__ import annotations

import email
import email.header
import email.utils
import hashlib
import imaplib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date as Date, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SHARED_KEY = "mailbox:messages"
USED_NAMESPACE = "mailbox"
PREFIXES = ("FEEDBACK", "LETTER", "PHOTO", "FRIEND", "TONIGHT", "IDEA")
MAX_MESSAGES = 200
MAX_BODY_CHARS = 4_000
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/heic": ".heic",
               "image/webp": ".webp", "image/gif": ".gif"}


@dataclass
class Message:
    uid: str                       # stable id, used to avoid printing twice
    kind: str                      # one of PREFIXES
    subject: str
    sender: str                    # display name where there is one
    address: str
    sent: Date | None
    body: str
    photos: list[Path] = field(default_factory=list)

    @property
    def age_days(self) -> int:
        return (Date.today() - self.sent).days if self.sent else 0


def _decode(raw: str | None) -> str:
    if not raw:
        return ""
    out = []
    for text, charset in email.header.decode_header(raw):
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return " ".join("".join(out).split())


def _body_of(message: email.message.Message) -> str:
    """The plain-text body, quoted replies and signatures trimmed off."""
    text = ""
    for part in message.walk():
        if part.get_content_type() != "text/plain":
            continue
        if "attachment" in (part.get("Content-Disposition") or ""):
            continue
        payload = part.get_payload(decode=True) or b""
        text = payload.decode(part.get_content_charset() or "utf-8",
                              errors="replace")
        break
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        # A phone's reply quotes the whole receipt back. Stop at the quote.
        if stripped.startswith(">") or re.match(r"^On .*wrote:$", stripped):
            break
        if stripped in ("--", "-- ", "Sent from my iPhone", "Get Outlook for iOS"):
            break
        lines.append(line.rstrip())
    return "\n".join(lines).strip()[:MAX_BODY_CHARS]


def _save_photos(message: email.message.Message, uid: str,
                 folder: Path) -> list[Path]:
    saved: list[Path] = []
    for part in message.walk():
        suffix = IMAGE_TYPES.get((part.get_content_type() or "").lower())
        if not suffix:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{uid}-{len(saved)}{suffix}"
        if not path.exists():
            path.write_bytes(payload)
        saved.append(path)
    return saved


def _kind(subject: str) -> str | None:
    head = subject.strip().upper()
    # A reply arrives as "Re: FEEDBACK ..." or "RE:FEEDBACK...".
    head = re.sub(r"^((RE|FW|FWD)\s*:\s*)+", "", head)
    for prefix in PREFIXES:
        if head.startswith(prefix):
            return prefix
    return None


def _uid(message: email.message.Message, fallback: bytes) -> str:
    """A stable id. Message-ID where there is one, else a hash of the message."""
    mid = (message.get("Message-ID") or "").strip()
    if mid:
        return hashlib.sha1(mid.encode("utf-8")).hexdigest()[:16]
    return hashlib.sha1(fallback).hexdigest()[:16]


def _sent(message: email.message.Message) -> Date | None:
    try:
        when = email.utils.parsedate_to_datetime(message.get("Date"))
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone().date()


def configured() -> bool:
    import config
    config.load_env()
    return all(os.environ.get(k) for k in
               ("QG_IMAP_HOST", "QG_IMAP_USER", "QG_IMAP_APP_PASSWORD"))


def fetch(photo_folder: Path | None = None) -> list[Message]:
    """Every routable message in the inbox, newest first. Empty on any problem."""
    import config
    config.load_env()
    if not configured():
        return []
    host = os.environ["QG_IMAP_HOST"]
    user = os.environ["QG_IMAP_USER"]
    # Providers show app passwords in blocks of four; both forms should work.
    password = os.environ["QG_IMAP_APP_PASSWORD"].replace(" ", "")
    folder = photo_folder or config.path("paths", "photos")

    out: list[Message] = []
    client = None
    try:
        client = imaplib.IMAP4_SSL(host, timeout=20)
        client.login(user, password)
        client.select("INBOX", readonly=True)     # readonly: never marks read
        typ, data = client.search(None, "ALL")
        if typ != "OK":
            return []
        ids = data[0].split()[-MAX_MESSAGES:]
        for num in reversed(ids):
            typ, payload = client.fetch(num, "(RFC822)")
            if typ != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            raw = payload[0][1]
            parsed = email.message_from_bytes(raw)
            subject = _decode(parsed.get("Subject"))
            kind = _kind(subject)
            if kind is None:
                continue                          # not ours; left alone
            name, address = email.utils.parseaddr(_decode(parsed.get("From")))
            uid = _uid(parsed, raw)
            out.append(Message(
                uid=uid, kind=kind, subject=subject,
                sender=name or address.split("@")[0], address=address,
                sent=_sent(parsed), body=_body_of(parsed),
                photos=_save_photos(parsed, uid, folder) if kind == "PHOTO" else [],
            ))
    except Exception as exc:  # noqa: BLE001 - an unreachable mailbox is no mail
        log.warning("mailbox unreachable: %s", exc)
        return out
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
    return out


def messages(ctx: Any, kind: str | None = None) -> list[Message]:
    """Today's mail, fetched once per run and shared between slots."""
    cached = ctx.shared.get(SHARED_KEY)
    if cached is None:
        cached = [] if ctx.offline else fetch()
        ctx.shared[SHARED_KEY] = cached
    return [m for m in cached if kind is None or m.kind == kind]


def used(store: Any) -> set[str]:
    """Message ids already printed, so nothing is delivered twice."""
    if store is None:
        return set()
    try:
        return set(store.fetch(USED_NAMESPACE, "used", []) or [])
    except Exception:  # noqa: BLE001
        return set()


def mark_used(ctx: Any, uid: str) -> None:
    if ctx.store is None or not ctx.shared.get("real_morning"):
        return
    try:
        seen = list(ctx.store.fetch(USED_NAMESPACE, "used", []) or [])
        if uid not in seen:
            ctx.store.put(USED_NAMESPACE, "used", (seen + [uid])[-500:])
    except Exception:  # noqa: BLE001
        pass


def unused(ctx: Any, kind: str) -> list[Message]:
    seen = used(ctx.store)
    return [m for m in messages(ctx, kind) if m.uid not in seen]


def address() -> str:
    import config
    config.load_env()
    return os.environ.get("QG_IMAP_USER", "")
