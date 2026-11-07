"""One-character card replies (k / s / d), claimed through post_gateway_admission."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

WINDOW_S = 120.0
CHOICES = {"k": "kept", "keep": "kept", "s": "shared", "share": "shared", "d": "discarded", "discard": "discarded"}
PRIVATE_CHAT_TYPES = {"dm", "private", "direct", "im"}


class ReplyWindows:
    """Open card windows. A reply is claimed only when it is unambiguous."""

    def __init__(self, window_s: float = WINDOW_S):
        self._open: dict[int, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._window = window_s

    def open(self, pair_id: int, platform: Optional[str], now: Optional[float] = None) -> None:
        with self._lock:
            self._open[pair_id] = ((platform or "").lower(), now if now is not None else time.time())

    def close(self, pair_id: int) -> None:
        with self._lock:
            self._open.pop(pair_id, None)

    def match(self, *, text: Any, platform: Any, source: Any, now: Optional[float] = None) -> Optional[tuple[int, str]]:
        """Return (pair_id, status) when this inbound message is a card reply, else None."""
        choice = CHOICES.get((text or "").strip().lower()) if isinstance(text, str) else None
        if choice is None:
            return None
        chat_type = (source or {}).get("chat_type") if isinstance(source, dict) else None
        if (chat_type or "").lower() not in PRIVATE_CHAT_TYPES:
            return None
        plat = (platform or "").lower()
        t = now if now is not None else time.time()
        with self._lock:
            for pid in [p for p, (_, opened) in self._open.items() if t - opened > self._window]:
                self._open.pop(pid, None)
            live = [pid for pid, (p, _) in self._open.items() if p == plat]
            if len(live) != 1:
                return None
            pid = live[0]
            self._open.pop(pid, None)
        return pid, choice
