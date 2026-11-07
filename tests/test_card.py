from ichor import card


def _pair(**kw):
    p = dict(id=14, kind="correction", feedback="no, use pnpm not npm",
             rejected="```bash\nnpm install && npm run build\n```", accepted="pnpm install && pnpm build",
             scrub_counts={"home_path": 1})
    p.update(kw)
    return p


def test_capture_card_matches_design():
    assert card.capture(_pair()) == (
        "ichor · captured pair #14\n"
        'you said: "no, use pnpm not npm"\n'
        "\n"
        "rejected\n"
        "  npm install && npm run build\n"
        "accepted\n"
        "  pnpm install && pnpm build\n"
        "\n"
        "scrubbed: 1 path · 0 secrets\n"
        "reply k keep · s share · d discard"
    )


def test_long_sides_are_trimmed():
    text = card.capture(_pair(accepted="\n".join(f"line {i}" for i in range(10))))
    assert "  line 5" in text and "  line 6" not in text
    assert "  ... (+4 lines)" in text


def test_long_lines_are_cut():
    text = card.capture(_pair(rejected="x" * 500))
    assert max(len(ln) for ln in text.splitlines()) <= 122


def test_retry_and_undo_lines():
    assert "you hit /retry" in card.capture(_pair(kind="retry", feedback=""))
    assert "you used /undo" in card.capture(_pair(kind="undo", feedback=""))


def test_collapsed():
    assert card.collapsed(14, "kept") == "ichor · pair #14 kept (private)"
    assert card.collapsed(14, "shared") == "ichor · pair #14 queued to share"
    assert card.collapsed(14, "discarded") == "ichor · pair #14 discarded"


def test_status_and_empty():
    out = card.status({"kept": 12, "shared": 3, "pending": 2, "discarded": 0},
                      [("package manager", 4), ("verbosity", 2)])
    assert out.splitlines()[0] == "ichor · 12 kept · 3 shared · 2 pending"
    assert "  package manager  4" in out and "  verbosity        2" in out
    assert card.status({"kept": 0, "shared": 0, "pending": 0, "discarded": 0}, []) == card.empty()


def test_no_em_dashes():
    for text in (card.capture(_pair()), card.empty(), card.status({"kept": 1}, [("a", 1)])):
        assert "\u2014" not in text
