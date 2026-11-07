import sqlite3

import pytest

from ichor.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(sqlite3.connect(tmp_path / "t.db", check_same_thread=False))


def _pair(**kw):
    base = dict(session_id="s1", turn_id="t1", platform="telegram", model="m", kind="correction",
                confidence="medium", reason="r", prompt="build it", rejected="npm run build",
                accepted="pnpm build", feedback="no, use pnpm", scrub_counts={"home_path": 1})
    base.update(kw)
    return base


def test_add_and_get(store):
    pid = store.add(_pair())
    got = store.get(pid)
    assert got["status"] == "pending" and got["accepted"] == "pnpm build"
    assert got["scrub_counts"] == {"home_path": 1}


def test_status_transitions_are_idempotent(store):
    pid = store.add(_pair())
    assert store.set_status(pid, "kept")
    assert store.set_status(pid, "kept")
    assert store.set_status(pid, "shared")
    assert store.get(pid)["status"] == "shared"
    assert not store.set_status(pid, "bogus")
    assert not store.set_status(999, "kept")


def test_counts_and_pending(store):
    a = store.add(_pair())
    b = store.add(_pair(session_id="s2"))
    store.set_status(a, "kept")
    assert store.counts() == {"pending": 1, "kept": 1, "shared": 0, "discarded": 0}
    assert store.latest_pending("s2")["id"] == b
    assert store.latest_pending("s1") is None
    assert store.oldest_pending()["id"] == b


def test_export_and_upload_sets(store):
    a, b, c = (store.add(_pair()) for _ in range(3))
    store.set_status(a, "kept")
    store.set_status(b, "shared")
    store.set_status(c, "discarded")
    assert [p["id"] for p in store.exportable()] == [a, b]
    assert [p["id"] for p in store.to_upload()] == [b]
    store.mark_uploaded([b], "https://hf.co/x")
    assert store.to_upload() == []  # sharing twice never re-uploads


def test_top_categories(store):
    for cat in ["package manager", "package manager", "verbosity"]:
        store.set_category(store.add(_pair()), cat)
    store.add(_pair(kind="retry"))
    assert store.top_categories() == [("package manager", 2), ("retry", 1), ("verbosity", 1)]


def test_forget_all_and_settings(store):
    store.add(_pair())
    assert store.forget_all() == 1
    assert store.counts()["pending"] == 0
    assert store.setting("off") is None
    store.set_setting("off", "1")
    store.set_setting("off", "0")
    assert store.setting("off") == "0"


def test_backfill_categories(store):
    a = store.add(_pair())
    b = store.add(_pair(category="kept label"))
    assert store.backfill_categories(lambda p: "wrong package manager") == 1
    assert store.get(a)["category"] == "wrong package manager"
    assert store.get(b)["category"] == "kept label"
