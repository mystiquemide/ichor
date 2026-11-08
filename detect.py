"""Correction detection: decide whether turn N+1 says turn N was wrong."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Turn:
    user: str
    assistant: str
    history_len: int


@dataclass(frozen=True)
class Signal:
    kind: str          # retry | undo | correction
    confidence: str    # high | medium | low
    reason: str
    prompt: str
    rejected: str
    accepted: str
    feedback: str = ""


_LEVELS = {"low": 0, "medium": 1, "high": 2}

# Openers that reject the previous answer. Anchored to the start of the message.
_OPENERS = re.compile(
    r"^\s*(?:no+\b(?!\s+(?:need|worries|problem|rush|pressure)\b)|nope\b|nah\b|wrong\b|incorrect\b|not quite\b|not what i\b|that'?s (?:not|wrong|incorrect)\b"
    r"|that is (?:not|wrong)\b|this is (?:not|wrong)\b|you (?:forgot|missed|ignored|didn'?t)\b|actually\b"
    r"|stop (?:doing|using|adding|making|saying|changing)\b|don'?t\b(?!\s+worry)|do not\b|why did you\b|i said\b|i asked\b|i told you\b|wait\b|hmm,? no\b|ugh\b)",
    re.IGNORECASE,
)

# Redirects that can appear anywhere in a short message.
_REDIRECTS = re.compile(
    r"\b(?:use \S+(?: \S+)? (?:not|instead of) \S+|instead of \S+|rather than \S+|not \S+,? (?:but|use)\b"
    r"|(?<!what )(?<!which )(?<!how )should (?:be|have been|use)\b|supposed to\b|redo\b|that broke\b"
    r"|still (?:wrong|broken|failing|too \w+)\b|^(?:this|that|it)(?:'s| is| was) too \w+\b"
    r"|doesn'?t work\b|didn'?t work\b|not working\b)",
    re.IGNORECASE,
)

# Replies to a question the agent asked, not corrections.
_ANSWER_WORDS = re.compile(r"^\s*(?:no|nope|nah|not now|no thanks|no thank you|don'?t)\W*(?:thanks?|thank you|need|bother)?\W*$", re.IGNORECASE)

_QUESTION_START = re.compile(r"^\s*(?:how|what|where|when|which|can you|could you|would you)\b", re.IGNORECASE)

_THANKS = re.compile(r"^\s*(?:thanks|thank you|thx|ty|great|perfect|nice|cool|ok|okay|got it"
                     r"|yes|yeah|yep|yup|sure|let'?s|and|also|dont worry|don'?t worry)\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _same_answer(a: str, b: str) -> bool:
    """Answers that differ only in case, spacing, punctuation or markdown are the same answer."""
    def key(t: str) -> str:
        return re.sub(r"[\W_]+", "", (t or "").lower())
    return key(a) == key(b)


def _ends_with_question(text: str) -> bool:
    tail = (text or "").strip()[-300:]
    return tail.endswith("?")


def _is_undo_shape(prev_len: int, cur_len: int) -> bool:
    """/undo N then a new prompt leaves history equal or 2 per extra undone turn shorter.
    A larger drop is compression or a reset, not a correction."""
    drop = prev_len - cur_len
    return 0 <= drop <= 6 and drop % 2 == 0


def detect(prev: Optional[Turn], cur: Turn, min_confidence: str = "medium") -> Optional[Signal]:
    """Return a Signal when cur shows prev's answer was rejected, else None."""
    if prev is None or not (prev.assistant or "").strip() or not (cur.assistant or "").strip():
        return None
    if _same_answer(prev.assistant, cur.assistant):
        return None

    grew = cur.history_len > prev.history_len
    same_text = _norm(prev.user) == _norm(cur.user) and bool(_norm(cur.user))

    signal: Optional[Signal] = None
    if same_text and not grew and prev.history_len - cur.history_len <= 6:
        signal = Signal("retry", "high", "same message re-sent, history did not grow",
                        prev.user, prev.assistant, cur.assistant)
    elif not grew and not same_text and _is_undo_shape(prev.history_len, cur.history_len):
        signal = Signal("undo", "medium", "history did not grow, new prompt",
                        cur.user, prev.assistant, cur.assistant)
    elif grew:
        signal = _correction(prev, cur)

    if signal is None or _LEVELS[signal.confidence] < _LEVELS.get(min_confidence, 1):
        return None
    return signal


def _correction(prev: Turn, cur: Turn) -> Optional[Signal]:
    text = (cur.user or "").strip()
    if not text or _THANKS.match(text):
        return None
    if _ends_with_question(prev.assistant) and _ANSWER_WORDS.match(text):
        return None  # "no thanks" to "Want me to deploy it?"

    opener = bool(_OPENERS.match(text))
    redirect = bool(_REDIRECTS.search(text))
    if redirect and not opener and _QUESTION_START.match(text):
        redirect = False  # "how do I fix it?" asks for help, it does not reject the answer
    short = len(text) < 200

    if opener and _ends_with_question(prev.assistant) and not redirect and len(text.split()) <= 3:
        return None  # bare "no" to a yes/no question

    if opener and (redirect or short):
        return Signal("correction", "medium", "rejecting opener", prev.user, prev.assistant, cur.assistant, text)
    if redirect and short:
        return Signal("correction", "medium", "redirect phrase", prev.user, prev.assistant, cur.assistant, text)
    if opener or redirect:
        return Signal("correction", "low", "weak correction cue in a long message",
                      prev.user, prev.assistant, cur.assistant, text)
    return None
