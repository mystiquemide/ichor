"""Ichor: turn the moments you correct Hermes into preference pairs."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger("ichor")

PLUGIN_NAME = "ichor"

_lock = threading.Lock()


def _data_dir():
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir(PLUGIN_NAME)


def _shape(value: Any) -> dict[str, Any]:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return {"len": len(text), "head": text[:80]}


def _on_post_llm_call(**kwargs: Any) -> None:
    """Record the shape of each finished turn. Observer only, never raises."""
    try:
        history = kwargs.get("conversation_history") or []
        row = {
            "ts": time.time(),
            "session_id": kwargs.get("session_id"),
            "turn_id": kwargs.get("turn_id"),
            "platform": kwargs.get("platform"),
            "model": kwargs.get("model"),
            "history_len": len(history),
            "roles_tail": [m.get("role") for m in history[-6:] if isinstance(m, dict)],
            "user": _shape(kwargs.get("user_message")),
            "assistant": _shape(kwargs.get("assistant_response")),
        }
        with _lock, open(_data_dir() / "turns.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        logger.debug("ichor post_llm_call observer failed", exc_info=True)


def _on_session_end(**kwargs: Any) -> None:
    return None


def _cmd_ichor(raw_args: str = "", **kwargs: Any) -> str:
    try:
        path = _data_dir() / "turns.jsonl"
        turns = sum(1 for _ in open(path, encoding="utf-8")) if path.exists() else 0
    except Exception:
        turns = 0
    if turns == 0:
        return 'ichor · no corrections yet\nlistening for "no...", /retry and /undo'
    return f"ichor · watching · {turns} turns observed\nno pairs yet"


def register(ctx) -> None:
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_command(
        "ichor",
        _cmd_ichor,
        description="Corrections captured as preference pairs",
        args_hint="[status]",
    )
