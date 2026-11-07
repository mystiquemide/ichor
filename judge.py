"""Optional mistake-category label from the session's own agent (ctx.side_question, fail closed)."""

from __future__ import annotations

import re
import threading
from typing import Any, Callable, Optional

CAPABILITY = "llm.side_question"

PROMPT = """In your previous answer the user pushed back. Name the type of mistake in 2 to 4 lowercase words.
Examples: wrong package manager, missing flag, wrong fact, too verbose, ignored instruction, unsafe default.
Reply with the label only, no punctuation.

Your answer they rejected:
{rejected}

What they said:
{feedback}

Your next answer:
{accepted}"""

_CLEAN = re.compile(r"[^a-z0-9 /+\-]")


def build_prompt(pair: dict[str, Any], limit: int = 1200) -> str:
    def cut(text: str) -> str:
        text = (text or "").strip()
        return text if len(text) <= limit else text[:limit] + " ..."
    return PROMPT.format(rejected=cut(pair.get("rejected", "")), feedback=cut(pair.get("feedback") or f"(used /{pair.get('kind')})"),
                         accepted=cut(pair.get("accepted", "")))


def clean_label(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    first = text.strip().splitlines()[0].lower().strip().strip("\"'`.")
    first = re.sub(r"^(label|category|mistake)\s*:\s*", "", first)
    words = _CLEAN.sub("", first).split()
    if not 1 <= len(words) <= 5:
        return None
    return " ".join(words)


def label(ctx: Any, token: Optional[str], pair: dict[str, Any], timeout: float = 20.0) -> Optional[str]:
    """Ask once. Returns None without the capability, token, or a usable answer."""
    if not token or ctx is None or not hasattr(ctx, "side_question"):
        return None
    has = getattr(ctx, "has_capability", None)
    if callable(has) and not has(CAPABILITY):
        return None
    try:
        return clean_label(ctx.side_question(token, build_prompt(pair), timeout=timeout))
    except Exception:
        return None


def label_in_background(ctx: Any, token: Optional[str], pair: dict[str, Any],
                        on_label: Callable[[int, str], None]) -> Optional[threading.Thread]:
    """Run label() off the turn thread so Hermes delivers its reply without waiting."""
    if not token:
        return None

    def work() -> None:
        result = label(ctx, token, pair)
        if result:
            on_label(pair["id"], result)

    thread = threading.Thread(target=work, name="ichor-judge", daemon=True)
    thread.start()
    return thread
