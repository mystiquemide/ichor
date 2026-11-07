import sqlite3

import pytest

from ichor.commands import run
from ichor.replies import ReplyWindows
from ichor.state import TurnState
from ichor.store import Store


@pytest.fixture
def env(tmp_path):
    store = Store(sqlite3.connect(tmp_path / "c.db", check_same_thread=False))
    return dict(store=store, state=TurnState(), windows=ReplyWindows())


def _add(store, **kw):
    pair = dict(session_id="s", kind="correction", prompt="p", rejected="npm", accepted="pnpm", feedback="no, pnpm")
    pair.update(kw)
    return store.add(pair)


def test_status_empty_and_filled(env):
    assert "no corrections yet" in run("", **env)
    _add(env["store"])
    assert run("", **env).startswith("ichor · 0 kept · 0 shared · 1 pending")


def test_review_opens_a_reply_window(env):
    pid = _add(env["store"])
    out = run("review", platform="telegram", **env)
    assert f"captured pair #{pid}" in out
    assert env["windows"].match(text="s", platform="telegram", source={"chat_type": "dm"}) == (pid, "shared")


def test_review_nothing(env):
    assert run("review", **env) == "ichor · nothing pending"


def test_keep_share_discard(env):
    pid = _add(env["store"])
    assert run(f"keep {pid}", **env) == f"ichor · pair #{pid} kept (private)"
    assert run(f"share #{pid}", **env) == f"ichor · pair #{pid} queued to share"
    assert env["store"].get(pid)["status"] == "shared"
    assert run("discard 999", **env) == "ichor · no pair #999"
    assert run("keep", **env) == "usage: /ichor keep <id>"


def test_off_on_session_and_global(env):
    assert run("off", session_id="s1", **env) == "ichor · off for this session"
    assert env["state"].is_off("s1")
    assert run("on", session_id="s1", **env) == "ichor · on for this session"
    assert not env["state"].is_off("s1")
    assert run("off --global", **env) == "ichor · off everywhere"
    assert env["store"].setting("global_off") == "1"
    assert "send a message first" in run("off", **env)


def test_forget_all_needs_confirmation(env):
    _add(env["store"])
    _add(env["store"])
    assert "confirm with /ichor forget-all yes" in run("forget-all", **env)
    assert sum(env["store"].counts().values()) == 2
    assert run("forget-all yes", **env) == "ichor · deleted 2 pairs"


def test_unknown_shows_help(env):
    assert run("bogus", **env).startswith("ichor commands")


def test_extra_subcommands(env):
    assert run("export now", extra={"export": lambda rest: f"exported {rest}"}, **env) == "exported ['now']"


def test_bare_share_uploads(env):
    assert run("share", extra={"upload": lambda rest: "uploaded"}, **env) == "uploaded"
    assert run("share", **env) == "usage: /ichor share <id>"


def test_set_repo_and_visibility(env):
    assert run("set repo my-pairs", **env) == "ichor · sharing to my-pairs"
    assert env["store"].setting("hf_repo") == "my-pairs"
    assert "can use letters" in run("set repo ../evil", **env)
    assert "can use letters" in run("set repo a/b", **env)
    assert run("set public", **env).startswith("ichor · sharing to a public repo")
    assert env["store"].setting("hf_private") == "0"
    assert run("set private", **env) == "ichor · sharing to a private repo"
    assert env["store"].setting("hf_private") == "1"
    assert run("set", **env).startswith("usage:")
