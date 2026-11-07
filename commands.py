"""/ichor subcommand router. Pure functions over a Store, a TurnState and ReplyWindows."""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from . import card

HELP = (
    "ichor commands\n"
    "  /ichor                 status and top mistakes\n"
    "  /ichor review          next pending pair\n"
    "  /ichor keep <id>       keep private\n"
    "  /ichor share <id>      queue for sharing\n"
    "  /ichor share           upload queued pairs to HF\n"
    "  /ichor discard <id>    drop it\n"
    "  /ichor export          write TRL + Atropos files\n"
    "  /ichor set repo <name> Hugging Face dataset name\n"
    "  /ichor set public      share to a public repo\n"
    "  /ichor set private     share to a private repo\n"
    "  /ichor off | on        pause or resume here\n"
    "  /ichor off --global    pause everywhere\n"
    "  /ichor forget-all yes  delete every pair"
)

_REPO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def _set(rest: list[str], store: Any) -> str:
    if rest[:1] == ["repo"] and len(rest) == 2:
        if not _REPO_NAME.match(rest[1]) or ".." in rest[1]:
            return "ichor · repo name can use letters, digits, '.', '_' and '-'"
        store.set_setting("hf_repo", rest[1])
        return f"ichor · sharing to {rest[1]}"
    if rest in (["public"], ["private"]):
        store.set_setting("hf_private", "0" if rest[0] == "public" else "1")
        note = "\nnew repos are created public; an existing repo keeps its visibility" if rest[0] == "public" else ""
        return f"ichor · sharing to a {rest[0]} repo{note}"
    return "usage: /ichor set repo <name> | public | private"


_STATUS_WORDS = {"keep": "kept", "k": "kept", "share": "shared", "s": "shared", "discard": "discarded", "d": "discarded"}


def run(raw_args: str, *, store: Any, state: Any, windows: Any, session_id: str = "", platform: str = "",
        extra: Optional[dict[str, Callable[[list[str]], str]]] = None) -> str:
    args = (raw_args or "").split()
    sub = args[0].lower() if args else "status"
    rest = args[1:]

    if sub in ("status", "stats"):
        return card.status(store.counts(), store.top_categories())
    if sub in ("help", "-h", "--help"):
        return HELP
    if sub == "review":
        pair = store.oldest_pending()
        if pair is None:
            return "ichor · nothing pending"
        windows.open(pair["id"], platform)
        return card.capture(pair)
    if sub == "share" and not rest and extra and "upload" in extra:
        return extra["upload"](rest)
    if sub in _STATUS_WORDS:
        if not rest or not rest[0].lstrip("#").isdigit():
            return f"usage: /ichor {sub} <id>"
        pair_id = int(rest[0].lstrip("#"))
        status = _STATUS_WORDS[sub]
        if not store.set_status(pair_id, status):
            return f"ichor · no pair #{pair_id}"
        windows.close(pair_id)
        return card.collapsed(pair_id, status)
    if sub in ("off", "on"):
        off = sub == "off"
        if "--global" in rest:
            store.set_setting("global_off", "1" if off else "0")
            return "ichor · off everywhere" if off else "ichor · on everywhere"
        if not session_id:
            return "ichor · no session here yet, send a message first"
        state.set_off(session_id, off)
        return card.off() if off else card.on()
    if sub == "set":
        return _set(rest, store)
    if sub == "forget-all":
        if rest[:1] != ["yes"]:
            n = sum(store.counts().values())
            return f"ichor · this deletes all {n} pairs\nconfirm with /ichor forget-all yes"
        return f"ichor · deleted {store.forget_all()} pairs"
    if extra and sub in extra:
        return extra[sub](rest)
    return HELP
