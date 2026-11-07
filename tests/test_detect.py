"""Detection precision on a labeled turn fixture (3 rows captured live on Telegram, the rest hand-labeled)."""

import json
from pathlib import Path

from ichor.detect import Turn, detect

FIXTURE = Path(__file__).parent / "fixtures" / "turns.jsonl"


def _rows():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def _run():
    results = []
    for row in _rows():
        prev, cur = Turn(**row["prev"]), Turn(**row["cur"])
        sig = detect(prev, cur)
        results.append((row, sig.kind if sig else "none"))
    return results


def test_fixture_size():
    assert len(_rows()) >= 40


def test_precision_and_recall():
    results = _run()
    tp = sum(1 for r, got in results if got != "none" and r["expect"] != "none")
    fp = [(r["id"], r["cur"]["user"], got) for r, got in results if got != "none" and r["expect"] == "none"]
    fn = [(r["id"], r["cur"]["user"], r["expect"]) for r, got in results if got == "none" and r["expect"] != "none"]
    precision = tp / (tp + len(fp)) if tp + len(fp) else 0.0
    recall = tp / (tp + len(fn)) if tp + len(fn) else 0.0
    print(f"\ndetection precision {precision:.2f} recall {recall:.2f} on {len(results)} labeled turns")
    if fp:
        print("false positives:", fp)
    if fn:
        print("false negatives:", fn)
    assert precision >= 0.9
    assert recall >= 0.8


def test_kind_is_correct_when_detected():
    wrong = [(r["id"], r["expect"], got) for r, got in _run() if got != "none" and r["expect"] != "none" and got != r["expect"]]
    assert not wrong, wrong


def test_identical_retry_is_skipped():
    a = Turn("hi", "same answer", 4)
    assert detect(a, Turn("hi", "same answer", 4)) is None


def test_no_previous_turn():
    assert detect(None, Turn("no, wrong", "ok", 2)) is None


def test_pair_sides():
    sig = detect(Turn("build it", "npm run build", 2), Turn("no, use pnpm", "pnpm build", 4))
    assert sig is not None
    assert (sig.prompt, sig.rejected, sig.accepted, sig.feedback) == ("build it", "npm run build", "pnpm build", "no, use pnpm")
