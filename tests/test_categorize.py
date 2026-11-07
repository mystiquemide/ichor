from ichor.categorize import rule_label


def lab(feedback, kind="correction"):
    return rule_label({"kind": kind, "feedback": feedback})


def test_live_corrections_get_useful_labels():
    assert lab("no, use pnpm not npm") == "wrong package manager"
    assert lab("no, use uv for that") == "wrong package manager"
    assert lab("no, use fd instead of find") == "wrong tool"
    assert lab("no, make it silent and follow redirects") == "missing option"
    assert lab("no, make it human readable and sorted by size") == "missing option"
    assert lab("nah, something more regal") == "wrong tone"
    assert lab("no, bind it to localhost only") == "unsafe default"


def test_other_categories():
    assert lab("still too long") == "too long"
    assert lab("wrong, it's Canberra") == "wrong fact"
    assert lab("I said use the v2 api") == "wrong tool"
    assert lab("you forgot to run it") == "ignored instruction"
    assert lab("it didn't work, table is missing") == "did not work"


def test_retry_undo_and_unknown():
    assert lab("", kind="retry") == "retried answer"
    assert lab("", kind="undo") == "changed the ask"
    assert lab("hmm no") is None


def test_exclusions_are_missing_options():
    for fb in ("no, exclude node_modules", "skip the hidden files", "without the header please"):
        assert rule_label({"kind": "correction", "feedback": fb}) == "missing option", fb
