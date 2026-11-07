"""Local mistake categories from the user's own words. The side_question judge overrides these when available."""

from __future__ import annotations

import re
from typing import Any, Optional

_PKG = {"npm", "pnpm", "yarn", "bun", "pip", "uv", "poetry", "pipx", "conda", "cargo", "brew", "apt"}

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("too long", re.compile(r"\b(?:too long|too verbose|shorter|shorten|less words|tl;?dr|be brief|concise)\b", re.I)),
    ("too short", re.compile(r"\b(?:too short|more detail|elaborate|expand on|longer)\b", re.I)),
    ("wrong tone", re.compile(r"\b(?:too (?:casual|formal|stiff)|tone|more (?:formal|casual|friendly)|regal|warmer|polite)\b", re.I)),
    ("wrong fact", re.compile(r"\b(?:wrong|incorrect|not true|that's false|it's actually|actually it's)\b", re.I)),
    ("ignored instruction", re.compile(r"\b(?:i said|i asked|i told you|as i said|you ignored|you forgot|you missed)\b", re.I)),
    ("did not work", re.compile(r"\b(?:didn'?t work|doesn'?t work|not working|still (?:broken|failing|wrong)|error|broke)\b", re.I)),
    ("unsafe default", re.compile(r"\b(?:localhost only|bind (?:it )?to localhost|privileged|root|sudo|unsafe|insecure)\b", re.I)),
    ("missing option", re.compile(r"\b(?:also|include|exclude|skip|ignore|without|add|with|make it|and (?:also )?(?:show|sort|follow))\b", re.I)),
]

_SWAP = re.compile(r"\b(?:use|try|with)\s+([\w./+-]+)(?:\s+(?:instead of|not|rather than|over)\s+([\w./+-]+))?", re.I)


def rule_label(pair: dict[str, Any]) -> Optional[str]:
    kind = pair.get("kind")
    if kind in ("retry", "undo"):
        return "retried answer" if kind == "retry" else "changed the ask"
    text = pair.get("feedback") or ""
    swap = _SWAP.search(text)
    if swap:
        wanted = swap.group(1).lower()
        return "wrong package manager" if wanted in _PKG else "wrong tool"
    for name, pattern in _RULES:
        if pattern.search(text):
            return name
    return None
