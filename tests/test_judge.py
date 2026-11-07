from ichor.judge import build_prompt, clean_label, label, label_in_background

PAIR = dict(id=7, kind="correction", rejected="npm run build", accepted="pnpm build", feedback="no, use pnpm")


class Ctx:
    def __init__(self, answer="Wrong package manager.", granted=True, boom=False):
        self.answer, self.granted, self.boom, self.calls = answer, granted, boom, []

    def has_capability(self, cap):
        return self.granted

    def side_question(self, token, prompt, timeout=15.0):
        self.calls.append((token, prompt))
        if self.boom:
            raise RuntimeError("x")
        return self.answer


def test_prompt_contains_all_sides():
    p = build_prompt(PAIR)
    assert "npm run build" in p and "pnpm build" in p and "no, use pnpm" in p
    assert "(used /retry)" in build_prompt(dict(PAIR, kind="retry", feedback=""))


def test_clean_label():
    assert clean_label("Wrong package manager.") == "wrong package manager"
    assert clean_label("Label: missing flag") == "missing flag"
    assert clean_label('"too verbose"\nbecause...') == "too verbose"
    assert clean_label("") is None
    assert clean_label("this answer is far too long to be a short category label") is None


def test_label_fails_closed():
    assert label(Ctx(granted=False), "t", PAIR) is None
    assert label(Ctx(), None, PAIR) is None
    assert label(Ctx(boom=True), "t", PAIR) is None
    assert label(None, "t", PAIR) is None
    assert label(Ctx(answer=None), "t", PAIR) is None


def test_label_happy_path():
    ctx = Ctx()
    assert label(ctx, "tok", PAIR) == "wrong package manager"
    assert ctx.calls[0][0] == "tok"


def test_background_calls_back():
    got = []
    t = label_in_background(Ctx(), "tok", PAIR, lambda pid, lab: got.append((pid, lab)))
    t.join(5)
    assert got == [(7, "wrong package manager")]
    assert label_in_background(Ctx(), None, PAIR, lambda *a: None) is None
