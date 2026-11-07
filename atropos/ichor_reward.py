"""Reward for Ichor preference pairs: closer to the accepted answer, further from the rejected one.

Pure Python, no dependencies. Score range is -1.0 to 1.0.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_FENCE = re.compile(r"^\s*```[\w+-]*\s*$", re.M)
_THINK = re.compile(r"<think>.*?</think>", re.S)


def normalize(text: str) -> str:
    text = _THINK.sub("", text or "")
    text = _FENCE.sub("", text)
    return " ".join(text.lower().split())


def similarity(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def reward(completion: str, accepted: str, rejected: str) -> float:
    """(sim to accepted - sim to rejected), scaled by how different the two answers are.

    Exactly the accepted answer scores 1.0, exactly the rejected one -1.0. Clipped to [-1, 1].
    """
    if not normalize(completion):
        return 0.0
    gap = max(1.0 - similarity(accepted, rejected), 0.05)
    raw = similarity(completion, accepted) - similarity(completion, rejected)
    return max(-1.0, min(1.0, raw / gap))
