"""Per-session memory of the last turn, so turn N+1 can be compared with turn N."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Optional

from .detect import Signal, Turn, detect

SKIP_PLATFORMS = {"cron", "subagent", "batch", "rl"}
MAX_SESSIONS = 256


class TurnState:
    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._last: "OrderedDict[str, Turn]" = OrderedDict()
        self._off: set[str] = set()
        self._lock = threading.Lock()
        self._max = max_sessions

    def observe(self, *, session_id: Optional[str], user_message: Any, assistant_response: Any,
                conversation_history: Any, platform: Optional[str] = None,
                min_confidence: str = "medium") -> Optional[Signal]:
        """Record this turn and return a Signal if it rejects the previous one."""
        if not session_id or (platform or "").lower() in SKIP_PLATFORMS:
            return None
        cur = Turn(
            user=user_message if isinstance(user_message, str) else "",
            assistant=assistant_response if isinstance(assistant_response, str) else "",
            history_len=len(conversation_history) if isinstance(conversation_history, list) else 0,
        )
        with self._lock:
            prev = self._last.get(session_id)
            self._last[session_id] = cur
            self._last.move_to_end(session_id)
            while len(self._last) > self._max:
                self._last.popitem(last=False)
            if session_id in self._off:
                return None
        return detect(prev, cur, min_confidence=min_confidence)

    def end(self, session_id: Optional[str]) -> None:
        with self._lock:
            self._last.pop(session_id or "", None)
            self._off.discard(session_id or "")

    def set_off(self, session_id: str, off: bool) -> None:
        with self._lock:
            (self._off.add if off else self._off.discard)(session_id)

    def is_off(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._off
