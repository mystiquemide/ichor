"""Scrubbing runs inside a turn hook, so it must stay fast on long, hostile text."""

import random
import string
import time

from ichor.scrub import scrub

LIMIT_S = 1.0


def _inputs():
    rng = random.Random(0)
    return {
        "prose": "word " * 10000,
        "no spaces": "a" * 50000,
        "digits and colons": "1234567890:" * 5000,
        "dots": "a." * 25000,
        "at signs": "x@" * 25000,
        "dots then at": "a." * 20000 + "@",
        "random printable": "".join(rng.choice(string.printable) for _ in range(50000)),
        "key assignments": "MY_API_KEY= " * 5000,
        "jwt prefix": "eyJ" + "a" * 20 + "." * 5000,
        "slashes": "/home/" * 8000,
        "url-ish": "http://" + "a:" * 20000,
        "capitals": "A" * 50000,
        "underscores": "_" * 50000,
        "key-ish run": "API_" * 12000,
        "plus digits": "+1 " * 15000,
        "token run": "TOKEN" * 10000,
        "dashes": "a-" * 25000,
        "password run": "PASSWORD=" * 6000,
        "huge": "a." * 200000,
    }


def test_scrub_is_fast_on_50k_hostile_inputs():
    slow = {}
    for name, text in _inputs().items():
        start = time.perf_counter()
        scrub(text)
        took = time.perf_counter() - start
        if took > LIMIT_S:
            slow[name] = round(took, 2)
    assert not slow, slow


def test_email_still_matches_after_bounds():
    out, counts = scrub("reach me at jane.doe+tag@mail.example.co.uk please")
    assert counts["email"] == 1 and "jane.doe" not in out


def test_detect_is_fast_on_long_messages():
    from ichor.detect import Turn, detect

    slow = {}
    for name, text in _inputs().items():
        start = time.perf_counter()
        detect(Turn("q", "answer " * 5000, 2), Turn(text, "other " * 5000, 4))
        took = time.perf_counter() - start
        if took > LIMIT_S:
            slow[name] = round(took, 2)
    assert not slow, slow


def test_long_input_is_cut():
    out, _ = scrub("x" * 30000)
    assert len(out) < 20100 and out.endswith("chars]")
