"""Local scrubber: removes secrets and personal data before a pair is stored."""

from __future__ import annotations

import re
from collections import Counter

# Order matters: specific token formats run before generic patterns.
_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED:private_key]"),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED:anthropic_key]"),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}"), "[REDACTED:openai_key]"),
    ("hf_token", re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "[REDACTED:hf_token]"),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})"), "[REDACTED:github_token]"),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED:aws_key]"),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "[REDACTED:slack_token]"),
    ("stripe_key", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"), "[REDACTED:stripe_key]"),
    ("google_key", re.compile(r"\bAIza[A-Za-z0-9_\-]{35}"), "[REDACTED:google_key]"),
    ("telegram_bot_token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b"), "[REDACTED:telegram_bot_token]"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "[REDACTED:jwt]"),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/]{16,}=*"), "Bearer [REDACTED:bearer]"),
    ("url_credentials", re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^\s:/@]+:[^\s/@]+@"), r"\1[REDACTED:credentials]@"),
    ("secret_assignment", re.compile(
        r"(?i)\b([A-Z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD)[A-Z0-9_]*)(\s*[=:]\s*)(['\"]?)([^\s'\"]{6,})\3"),
        r"\1\2\3[REDACTED:secret]\3"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[REDACTED:email]"),
    ("ipv4", re.compile(r"\b(?!(?:127|0)\.)(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"), "[REDACTED:ip]"),
    ("phone", re.compile(r"(?<![\w.])\+\d{1,3}[\s\-]?\(?\d{2,4}\)?(?:[\s\-]?\d{3,4}){2}(?![\w.])"), "[REDACTED:phone]"),
    ("home_path", re.compile(r"(?:/home/|/Users/)[A-Za-z0-9._\-]+|[A-Za-z]:\\Users\\[A-Za-z0-9._\-]+"), "~"),
]

SECRET_KINDS = {
    "private_key", "anthropic_key", "openai_key", "hf_token", "github_token", "aws_key",
    "slack_token", "stripe_key", "google_key", "telegram_bot_token", "jwt", "bearer",
    "url_credentials", "secret_assignment",
}


def scrub(text: str | None) -> tuple[str, Counter]:
    """Return (scrubbed_text, counts by kind). Never raises on str input."""
    counts: Counter = Counter()
    if not text:
        return text or "", counts
    out = text
    for kind, pattern, repl in _RULES:
        out, n = pattern.subn(repl, out)
        if n:
            counts[kind] += n
    return out, counts


def summarize(counts: Counter) -> str:
    """Card line, e.g. '1 path · 2 secrets'."""
    secrets = sum(v for k, v in counts.items() if k in SECRET_KINDS)
    paths = counts.get("home_path", 0)
    personal = sum(counts.get(k, 0) for k in ("email", "ipv4", "phone"))
    parts = [f"{paths} path{'s' if paths != 1 else ''}", f"{secrets} secret{'s' if secrets != 1 else ''}"]
    if personal:
        parts.append(f"{personal} personal")
    return " · ".join(parts)
