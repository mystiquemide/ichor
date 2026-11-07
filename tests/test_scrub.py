"""Scrubber recall tests. Secrets are assembled at runtime so no real-format token sits in the repo."""

from ichor.scrub import scrub, summarize

A = "a1B2c3D4e5"  # 10-char filler


def _cases():
    return [
        ("openai_key", "key is sk-proj-" + A * 4),
        ("openai_key", "sk-" + A * 3),
        ("anthropic_key", "sk-ant-api03-" + A * 5),
        ("hf_token", "hf_" + A * 3 + "xyzw"),
        ("github_token", "token ghp_" + A * 4),
        ("github_token", "github_pat_" + A * 7),
        ("aws_key", "AKIA" + "ABCDEFGH12345678"),
        ("slack_token", "xoxb-" + "1234567890-" + A),
        ("stripe_key", "sk_" + "live_" + A * 2),
        ("google_key", "AIza" + A * 3 + "abcde"),
        ("telegram_bot_token", "1234567890:" + A * 3 + "abcde"),
        ("jwt", "eyJ" + A + "." + "eyJ" + A + "." + A),
        ("bearer", "Authorization: Bearer " + A * 3),
        ("url_credentials", "postgres://admin:" + "hunter2pass" + "@db.example.com/app"),
        ("secret_assignment", "DATABASE_PASSWORD=" + "s3cr3tValue!"),
        ("secret_assignment", "export MY_API_KEY='" + A + "'"),
        ("private_key", "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"),
        ("email", "mail me at jane.doe@example.org"),
        ("ipv4", "server at 203.0.113.7 is up"),
        ("phone", "call +44 20 7946 0958 today"),
        ("home_path", "see /home/alice/projects/app"),
        ("home_path", "open /Users/jane/Desktop"),
        ("home_path", r"C:\Users\jane\file.txt"),
    ]


def test_every_secret_format_is_removed():
    missed = []
    for kind, text in _cases():
        out, counts = scrub(text)
        if counts.get(kind, 0) < 1:
            missed.append((kind, text, out))
    recall = 1 - len(missed) / len(_cases())
    print(f"scrubber recall {recall:.2f} on {len(_cases())} cases")
    assert not missed, missed


def test_secret_values_never_survive():
    for _kind, text in _cases():
        out, _ = scrub(text)
        for token in (A * 3, "hunter2pass", "s3cr3tValue!", "jane.doe@example.org", "203.0.113.7", "/home/alice"):
            if token in text:
                assert token not in out, (text, out)


def test_plain_code_is_untouched():
    code = "pnpm install --frozen-lockfile && pnpm build\nprint('hello')\nfor i in range(10): pass"
    out, counts = scrub(code)
    assert out == code
    assert not counts


def test_localhost_is_not_an_ip_leak():
    out, counts = scrub("curl http://127.0.0.1:8080/health")
    assert "127.0.0.1" in out
    assert not counts.get("ipv4")


def test_summary_line():
    _, counts = scrub("/home/alice/a and sk-" + A * 3)
    assert summarize(counts) == "1 path · 1 secret"


def test_empty_input():
    assert scrub("") == ("", {})
    assert scrub(None)[0] == ""
