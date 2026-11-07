"""Plain-text cards. Same text on Telegram, Discord, Slack and the CLI."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .scrub import summarize

MAX_LINES = 6
MAX_LINE = 120

_FENCE = re.compile(r"^\s*```[\w+-]*\s*$")


def _side(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if not _FENCE.match(ln)]
    lines = [ln.rstrip() for ln in lines if ln.strip()] or ["(empty)"]
    shown = [("  " + (ln if len(ln) <= MAX_LINE else ln[: MAX_LINE - 3] + "...")) for ln in lines[:MAX_LINES]]
    extra = len(lines) - MAX_LINES
    if extra > 0:
        shown.append(f"  ... (+{extra} line{'s' if extra != 1 else ''})")
    return "\n".join(shown)


def _quote(text: str, limit: int = 80) -> str:
    one = " ".join((text or "").split())
    return one if len(one) <= limit else one[: limit - 3] + "..."


_KIND_LINE = {
    "correction": None,
    "retry": "you hit /retry",
    "undo": "you used /undo and asked again",
}


def capture(pair: dict[str, Any]) -> str:
    kind = pair.get("kind", "correction")
    said = f'you said: "{_quote(pair.get("feedback", ""))}"' if kind == "correction" and pair.get("feedback") else _KIND_LINE.get(kind) or ""
    parts = [f"ichor · captured pair #{pair['id']}"]
    if said:
        parts.append(said)
    parts += [
        "",
        "rejected",
        _side(pair.get("rejected", "")),
        "accepted",
        _side(pair.get("accepted", "")),
        "",
        f"scrubbed: {summarize(pair.get('scrub_counts') or {})}",
        "reply k keep · s share · d discard",
    ]
    return "\n".join(parts)


_COLLAPSED = {
    "kept": "kept (private)",
    "shared": "queued to share",
    "discarded": "discarded",
    "pending": "pending",
}


def collapsed(pair_id: int, status: str) -> str:
    return f"ichor · pair #{pair_id} {_COLLAPSED.get(status, status)}"


def status(counts: dict[str, int], top: Iterable[tuple[str, int]]) -> str:
    if not any(counts.values()):
        return empty()
    head = f"ichor · {counts.get('kept', 0)} kept · {counts.get('shared', 0)} shared · {counts.get('pending', 0)} pending"
    top = list(top)
    lines = [head]
    if top:
        width = max(len(name) for name, _ in top)
        lines.append("top mistakes")
        lines += [f"  {name.ljust(width)}  {n}" for name, n in top]
    lines.append("/ichor review · export · share")
    return "\n".join(lines)


def empty() -> str:
    return 'ichor · no corrections yet\nlistening for "no...", /retry and /undo'


def off() -> str:
    return "ichor · off for this session"


def on() -> str:
    return "ichor · on for this session"
