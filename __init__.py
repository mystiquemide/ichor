"""Ichor: turn the moments you correct Hermes into preference pairs."""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from typing import Any, Optional

from . import card, commands, export_atropos, export_dpo, judge, share_hf
from .categorize import rule_label
from .replies import ReplyWindows
from .scrub import scrub
from .state import TurnState
from .store import Store

logger = logging.getLogger("ichor")

PLUGIN_NAME = "ichor"

_state = TurnState()
_store: Optional[Store] = None
_store_lock = threading.Lock()
_ctx: Any = None
_cards: dict[int, Any] = {}  # pair id -> message handle, for in-place edits
_CARDS_MAX = 64
_windows = ReplyWindows()


def _get_store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store.open_default()
            _import_legacy_jsonl(_store)
            _store.backfill_categories(rule_label)
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
        "scrub_counts": dict(total), "category": rule_label({"kind": signal.kind, **fields}), **fields,
    })


def _on_post_llm_call(**kwargs: Any) -> None:
    """Observer only: compare this turn with the previous one. Never raises."""
    try:
        if _get_store().setting("global_off") == "1":
            return
        signal = _state.observe(
            session_id=kwargs.get("session_id"),
            user_message=kwargs.get("user_message"),
            assistant_response=kwargs.get("assistant_response"),
            conversation_history=kwargs.get("conversation_history"),
            platform=kwargs.get("platform"),
        )
        if signal is not None:
            pair_id = _record(signal, session_id=kwargs.get("session_id"), turn_id=kwargs.get("turn_id"),
                              platform=kwargs.get("platform"), model=kwargs.get("model"))
            if _post_card(pair_id):
                _windows.open(pair_id, kwargs.get("platform"))
            pair = _get_store().get(pair_id)
            if pair is not None:
                judge.label_in_background(_ctx, kwargs.get("side_question_token"), pair,
                                          lambda pid, lab: _get_store().set_category(pid, lab))
    except Exception:
        logger.debug("ichor post_llm_call observer failed", exc_info=True)


def _post_card(pair_id: int) -> bool:
    """Post the capture card into the current conversation. Refused outside a live gateway: the pair stays pending."""
    if _ctx is None or not hasattr(_ctx, "post_message"):
        return False
    pair = _get_store().get(pair_id)
    if pair is None:
        return False
    handle = _ctx.post_message(card.capture(pair))
    if not getattr(handle, "ok", False):
        logger.debug("ichor card not posted: %s", getattr(handle, "result", None))
        return False
    _cards[pair_id] = handle
    while len(_cards) > _CARDS_MAX:
        _cards.pop(next(iter(_cards)))
    return True


async def _on_post_gateway_admission(**kwargs: Any) -> Optional[dict]:
    """Claim a one-character card reply. Anything else returns None and reaches the agent."""
    try:
        hit = _windows.match(text=kwargs.get("text"), platform=kwargs.get("platform"), source=kwargs.get("source"))
        if hit is None:
            return None
        pair_id, status = hit
        if not _get_store().set_status(pair_id, status):
            return None
        handle = _cards.pop(pair_id, None)
        text = card.collapsed(pair_id, status)
        if handle is not None and hasattr(handle, "aedit"):
            await handle.aedit(text)
            if getattr(handle, "ok", False):
                return {"action": "handled"}
        return {"action": "handled", "reply": text}
    except Exception:
        logger.debug("ichor admission hook failed", exc_info=True)
        return None


def _on_session_finalize(**kwargs: Any) -> None:
    """Teardown of a session. Note: on_session_end fires after every turn, so it is not used."""
    try:
        _state.end(kwargs.get("session_id"))
    except Exception:
        logger.debug("ichor on_session_finalize failed", exc_info=True)


def _cmd_ichor(raw_args: str = "", *, session_id: str = "", platform: str = "", **kwargs: Any) -> str:
    try:
        return commands.run(raw_args, store=_get_store(), state=_state, windows=_windows,
                            session_id=session_id or "", platform=platform or "",
                            extra={"export": _export, "upload": _upload})
    except Exception:
        logger.debug("ichor command failed", exc_info=True)
        return "ichor · something went wrong, see agent.log"


def _export(_rest: list) -> str:
    import os

    pairs = _get_store().exportable()
    if not pairs:
        return "ichor · nothing to export yet\nkeep or share a pair first"
    out_dir = export_dpo.default_dir()
    path, n = export_dpo.write(pairs, out_dir)
    env_dir, _ = export_atropos.write(pairs, out_dir)
    home = os.path.expanduser("~")
    return (f"ichor · exported {n} pair{'s' if n != 1 else ''}\n"
            f"  dpo      {str(path).replace(home, '~', 1)}\n"
            f"  atropos  {str(env_dir).replace(home, '~', 1)}/")


def _upload(_rest: list) -> str:
    store = _get_store()
    pairs = store.to_upload()
    private = store.setting("hf_private", "1") != "0"
    try:
        url, n = share_hf.share(pairs, repo_name=store.setting("hf_repo", "ichor-pairs") or "ichor-pairs",
                                private=private)
    except share_hf.ShareError as err:
        return f"ichor · {err}"
    store.mark_uploaded([p["id"] for p in pairs], url)
    return f"ichor · shared {n} pair{'s' if n != 1 else ''} ({'private' if private else 'public'} repo)\n{url}"


def register(ctx) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_finalize", _on_session_finalize)
    ctx.register_hook("post_gateway_admission", _on_post_gateway_admission)
    ctx.register_command(
        "ichor",
        _cmd_ichor,
        description="Corrections captured as preference pairs",
        args_hint="[status|review|keep|share|discard|off|on|help]",
    )
