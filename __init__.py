"""Ichor: turn the moments you correct Hermes into preference pairs."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from typing import Any

from .scrub import scrub, summarize
from .state import TurnState

logger = logging.getLogger("ichor")

PLUGIN_NAME = "ichor"

_state = TurnState()
_write_lock = threading.Lock()


def _data_dir():
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir(PLUGIN_NAME)


def _record(signal, *, session_id, turn_id, platform, model) -> dict:
    fields: dict[str, str] = {}
    total: Counter = Counter()
    for name in ("prompt", "rejected", "accepted", "feedback"):
        text, counts = scrub(getattr(signal, name))
        fields[name] = text
        total += counts
    row = {
        "ts": time.time(), "session_id": session_id, "turn_id": turn_id, "platform": platform,
        "model": model, "kind": signal.kind, "confidence": signal.confidence, "reason": signal.reason,
        "scrub": dict(total), "scrub_summary": summarize(total), **fields,
    }
    with _write_lock, open(_data_dir() / "signals.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


def _on_post_llm_call(**kwargs: Any) -> None:
    """Observer only: compare this turn with the previous one. Never raises."""
    try:
        signal = _state.observe(
            session_id=kwargs.get("session_id"),
            user_message=kwargs.get("user_message"),
            assistant_response=kwargs.get("assistant_response"),
            conversation_history=kwargs.get("conversation_history"),
            platform=kwargs.get("platform"),
        )
        if signal is not None:
            _record(signal, session_id=kwargs.get("session_id"), turn_id=kwargs.get("turn_id"),
                    platform=kwargs.get("platform"), model=kwargs.get("model"))
    except Exception:
        logger.debug("ichor post_llm_call observer failed", exc_info=True)


def _on_session_finalize(**kwargs: Any) -> None:
    """Teardown of a session. Note: on_session_end fires after every turn, so it is not used."""
    try:
        _state.end(kwargs.get("session_id"))
    except Exception:
        logger.debug("ichor on_session_finalize failed", exc_info=True)


def _cmd_ichor(raw_args: str = "", **kwargs: Any) -> str:
    try:
        path = _data_dir() / "signals.jsonl"
        n = sum(1 for _ in open(path, encoding="utf-8")) if path.exists() else 0
    except Exception:
        n = 0
    if n == 0:
        return 'ichor · no corrections yet\nlistening for "no...", /retry and /undo'
    return f"ichor · {n} pair{'s' if n != 1 else ''} captured"


def register(ctx) -> None:
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_finalize", _on_session_finalize)
    ctx.register_command(
        "ichor",
        _cmd_ichor,
        description="Corrections captured as preference pairs",
        args_hint="[status]",
    )
