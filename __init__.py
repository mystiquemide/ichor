"""Ichor: turn the moments you correct Hermes into preference pairs."""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from typing import Any, Optional

from . import card
from .scrub import scrub
from .state import TurnState
from .store import Store

logger = logging.getLogger("ichor")

PLUGIN_NAME = "ichor"

_state = TurnState()
_store: Optional[Store] = None
_store_lock = threading.Lock()


def _get_store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store.open_default()
            _import_legacy_jsonl(_store)
        return _store


def _import_legacy_jsonl(store: Store) -> None:
    """One-time move of pairs captured before the SQLite store existed."""
    try:
        from plugins.plugin_storage import plugin_data_dir

        path = plugin_data_dir(PLUGIN_NAME) / "signals.jsonl"
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row["scrub_counts"] = row.pop("scrub", {})
                store.add(row)
        path.rename(path.with_suffix(".jsonl.imported"))
    except Exception:
        logger.debug("ichor legacy import failed", exc_info=True)


def _record(signal, *, session_id, turn_id, platform, model) -> int:
    fields: dict[str, str] = {}
    total: Counter = Counter()
    for name in ("prompt", "rejected", "accepted", "feedback"):
        text, counts = scrub(getattr(signal, name))
        fields[name] = text
        total += counts
    return _get_store().add({
        "session_id": session_id, "turn_id": turn_id, "platform": platform, "model": model,
        "kind": signal.kind, "confidence": signal.confidence, "reason": signal.reason,
        "scrub_counts": dict(total), **fields,
    })


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
        c = _get_store().counts()
    except Exception:
        logger.debug("ichor status failed", exc_info=True)
        return "ichor · store unavailable"
    return card.status(c, _get_store().top_categories())


def register(ctx) -> None:
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_finalize", _on_session_finalize)
    ctx.register_command(
        "ichor",
        _cmd_ichor,
        description="Corrections captured as preference pairs",
        args_hint="[status]",
    )
