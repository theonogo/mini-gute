"""Slot 24 - Dev knowledge.

One genuinely useful thing. `SLOTS.md` sets the bar precisely and it is worth
restating because it is easy to drift off: **something the reader could
plausibly ship this week.** Interesting and useful, never obscure, never code
golf, never trivia.

**Range across the whole surface, not just CSS.** The catalogue names CSS
properties, git flags, shell one-liners, browser APIs and editor tricks, and
lists CSS first only because it is the obvious one. Entries here carry a `kind`
and the day picks a kind before it picks an entry, so the slot cannot silently
become a CSS tip-of-the-day - which is what happens when you draw uniformly from
a list somebody kept adding CSS to.

The snippet prints in the embedded monospace and is verbatim: a persona
rephrasing a shell command is a persona breaking it. The narrator writes the
sentence saying why you would want it.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# (kind, snippet, what it does)
ENTRIES: list[tuple[str, str, str]] = [
    # --- git ---
    ("git", "git switch -", "jumps back to the previous branch, like `cd -`"),
    ("git", "git commit --fixup <sha>",
     "makes a commit that `git rebase -i --autosquash` will fold into that one "
     "automatically"),
    ("git", "git log -S'someString'",
     "finds the commits where a string was actually added or removed, not just "
     "mentioned"),
    ("git", "git reflog",
     "lists every position HEAD has held, so a 'lost' commit after a bad reset "
     "is almost always still there"),
    ("git", "git add -p",
     "stages hunk by hunk, which turns one sprawling change into several honest "
     "commits"),
    ("git", "git bisect start / bad / good <sha>",
     "binary-searches history for the commit that broke something"),
    ("git", "git worktree add ../hotfix main",
     "checks out a second branch into its own directory, so you can fix "
     "something without stashing what you were doing"),
    ("git", "git blame -w -C",
     "ignores whitespace and follows code moved between files, which is the "
     "difference between blame being useful and being noise"),

    # --- shell ---
    ("shell", "!$",
     "the last argument of the previous command - `mkdir long/path` then "
     "`cd !$`"),
    ("shell", "ctrl-r",
     "searches backwards through shell history as you type"),
    ("shell", "cmd1 <(cmd2)",
     "process substitution: hands one command's output to another as if it "
     "were a file, so `diff <(ls a) <(ls b)` works"),
    ("shell", "trap 'cleanup' EXIT",
     "runs cleanup when a script exits, however it exits"),
    ("shell", "set -euo pipefail",
     "makes a bash script stop at the first error instead of carrying on with "
     "bad state"),

    # --- css ---
    ("css", "text-wrap: balance",
     "evens out the line lengths in a heading, so no single word is left alone "
     "on the last line"),
    ("css", ":has(> img)",
     "styles a parent based on its children - the long-requested parent "
     "selector, now supported everywhere"),
    ("css", "aspect-ratio: 16 / 9",
     "reserves the right shape before an image loads, which is most of what "
     "causes layout shift"),
    ("css", "scroll-margin-top: 5rem",
     "stops an anchor target landing underneath a sticky header"),
    ("css", "clamp(1rem, 2vw + 0.5rem, 2rem)",
     "a size that scales with the viewport but cannot escape its bounds - "
     "responsive type without breakpoints"),
    ("css", "overscroll-behavior: contain",
     "stops a scrolled-to-the-end modal from scrolling the page behind it"),

    # --- browser and web APIs ---
    ("browser", "structuredClone(obj)",
     "a real deep copy, built in - handles Dates, Maps and cycles, which "
     "JSON round-tripping does not"),
    ("browser", "Intl.RelativeTimeFormat",
     "renders '3 days ago' correctly in any language, without a date library"),
    ("browser", "AbortController",
     "cancels a fetch - the standard way to drop a request when the user types "
     "again or navigates away"),
    ("browser", "IntersectionObserver",
     "tells you when an element enters the viewport, without a scroll handler "
     "firing sixty times a second"),
    ("browser", "navigator.sendBeacon(url, data)",
     "posts data during page unload, when a normal fetch gets killed"),
    ("browser", "<dialog> and showModal()",
     "a real modal with focus trapping and escape-to-close, no library"),

    # --- editor and tooling ---
    ("editor", "ctrl-shift-L (VS Code)",
     "selects every occurrence of the current selection and edits them all at "
     "once"),
    ("editor", "python -m json.tool",
     "pretty-prints JSON from a pipe, with no dependency and no website"),
    ("editor", "python -m http.server",
     "serves the current directory over HTTP, which is usually all a static "
     "site needs to be tested properly"),
    ("editor", "git diff --word-diff",
     "shows changes word by word rather than line by line, which makes prose "
     "diffs readable"),
]

KINDS = sorted({kind for kind, _, _ in ENTRIES})


@register
class DevKnowledge(Slot):
    spec = SlotSpec(id=24, name="Dev knowledge", tier="uncommon",
                    paper_mm=22, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        # Kind first, then entry within it. Drawing straight from ENTRIES would
        # weight the slot towards whichever category has most rows, and the
        # catalogue asks for range explicitly.
        kind = rng.choice(KINDS)
        _, snippet, does = rng.choice([e for e in ENTRIES if e[0] == kind])
        return SlotResult(
            head="Worth Knowing",
            body=f'<code class="snippet">{_escape(snippet)}</code>',
            fine=does[0].upper() + does[1:],
            brief={"verbatim": True,
                   "kind": kind, "snippet": snippet, "does": does,
                   "instruction": "Name this section in voice. The snippet is "
                                  "code and prints exactly as written - a "
                                  "rephrased command is a broken command."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))
