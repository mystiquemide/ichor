from ichor.state import TurnState


def _turn(state, sid, user, assistant, hist, platform="telegram"):
    return state.observe(session_id=sid, user_message=user, assistant_response=assistant,
                         conversation_history=[{}] * hist, platform=platform)


def test_live_sequence_from_telegram():
    s = TurnState()
    assert _turn(s, "a", "install and build", "npm ci && npm run build", 2) is None
    sig = _turn(s, "a", "no, use pnpm not npm", "pnpm install && pnpm build", 6)
    assert sig and sig.kind == "correction" and sig.rejected.startswith("npm")
    assert _turn(s, "a", "hello world", "print('hi')", 8) is None
    assert _turn(s, "a", "hello world", "print('hi')", 8) is None  # identical retry
    assert _turn(s, "a", "rivers in africa", "Nile", 10) is None
    sig = _turn(s, "a", "rivers in asia", "Yangtze", 10)
    assert sig and sig.kind == "undo"


def test_sessions_do_not_mix():
    s = TurnState()
    _turn(s, "a", "build", "npm run build", 2)
    assert _turn(s, "b", "no, use pnpm", "pnpm build", 4) is None


def test_cron_and_missing_session_are_skipped():
    s = TurnState()
    _turn(s, "c", "build", "npm", 2, platform="cron")
    assert _turn(s, "c", "no, use pnpm", "pnpm", 4, platform="cron") is None
    assert s.observe(session_id=None, user_message="x", assistant_response="y", conversation_history=[]) is None


def test_off_switch_and_end():
    s = TurnState()
    s.set_off("a", True)
    _turn(s, "a", "build", "npm", 2)
    assert _turn(s, "a", "no, use pnpm", "pnpm", 4) is None
    s.set_off("a", False)
    assert _turn(s, "a", "no, use yarn", "yarn", 6).kind == "correction"
    s.end("a")
    assert _turn(s, "a", "no, use bun", "bun", 8) is None


def test_bounded_memory():
    s = TurnState(max_sessions=3)
    for i in range(10):
        _turn(s, str(i), "q", "a", 2)
    assert len(s._last) == 3


def test_bad_inputs_never_raise():
    s = TurnState()
    assert s.observe(session_id="x", user_message=None, assistant_response=42, conversation_history=None) is None
