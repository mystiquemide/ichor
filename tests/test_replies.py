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


def test_session_key_keeps_chats_apart():
    w = ReplyWindows()
    w.open(3, "telegram", now=0, session_key="agent:main:telegram:dm:A")
    # user B in their own DM: the only open card belongs to A, so B's "k" is not claimed
    assert w.match(text="k", platform="telegram", source=DM, now=1, session_key="agent:main:telegram:dm:B") is None
    assert w.match(text="k", platform="telegram", source=DM, now=2, session_key="agent:main:telegram:dm:A") == (3, "kept")


def test_same_chat_reply_answers_newest_card():
    w = ReplyWindows()
    w.open(3, "telegram", now=0, session_key="A")
    w.open(4, "telegram", now=5, session_key="A")
    w.open(9, "telegram", now=6, session_key="B")
    assert w.match(text="d", platform="telegram", source=DM, now=7, session_key="A") == (4, "discarded")


def test_clear():
    w = ReplyWindows()
    w.open(3, "telegram", now=0)
    w.clear()
    assert w.match(text="k", platform="telegram", source=DM, now=1) is None
