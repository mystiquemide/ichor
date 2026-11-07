from ichor.replies import ReplyWindows

DM = {"chat_type": "dm", "chat_id": "1"}


def test_claims_single_open_card():
    w = ReplyWindows()
    w.open(3, "telegram", now=100)
    assert w.match(text=" K ", platform="telegram", source=DM, now=110) == (3, "kept")
    assert w.match(text="k", platform="telegram", source=DM, now=111) is None  # closed after use


def test_choices():
    for text, status in [("s", "shared"), ("share", "shared"), ("d", "discarded"), ("keep", "kept")]:
        w = ReplyWindows()
        w.open(1, "telegram", now=0)
        assert w.match(text=text, platform="telegram", source=DM, now=1) == (1, status)


def test_ordinary_messages_pass_through():
    w = ReplyWindows()
    w.open(3, "telegram", now=100)
    for text in ["ok", "kk", "keep going", "s3 bucket", "", None, 42]:
        assert w.match(text=text, platform="telegram", source=DM, now=101) is None
    assert w.match(text="k", platform="telegram", source=DM, now=102) == (3, "kept")


def test_window_expires():
    w = ReplyWindows(window_s=120)
    w.open(3, "telegram", now=0)
    assert w.match(text="k", platform="telegram", source=DM, now=121) is None


def test_groups_are_never_claimed():
    w = ReplyWindows()
    w.open(3, "telegram", now=0)
    assert w.match(text="k", platform="telegram", source={"chat_type": "group"}, now=1) is None
    assert w.match(text="k", platform="telegram", source=None, now=1) is None


def test_ambiguous_windows_are_not_claimed():
    w = ReplyWindows()
    w.open(3, "telegram", now=0)
    w.open(4, "telegram", now=1)
    assert w.match(text="k", platform="telegram", source=DM, now=2) is None


def test_other_platform_not_claimed():
    w = ReplyWindows()
    w.open(3, "discord", now=0)
    assert w.match(text="k", platform="telegram", source=DM, now=1) is None
