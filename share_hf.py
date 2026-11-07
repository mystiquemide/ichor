"""Upload shared pairs to a Hugging Face dataset repo with the Hub HTTP API (stdlib only)."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from .export_dpo import to_record

HUB = "https://huggingface.co"
TIMEOUT = 30

CARD = """---
license: cc-by-4.0
tags:
- ichor
- preference
- dpo
- hermes-agent
configs:
- config_name: default
  data_files: "data/*.jsonl"
---

# {repo}

Preference pairs captured by [Ichor](https://github.com/mystiquemide/ichor) from real Hermes Agent sessions.
Each row is a moment the user corrected the agent: `rejected` is the answer they pushed back on, `chosen` is
the answer they accepted, and `metadata.feedback` is what they said. Every row was confirmed by the user and
scrubbed locally for secrets, emails, IPs, phone numbers and home paths before upload.

Format: TRL conversational preference (`prompt`, `chosen`, `rejected` as message lists).
"""


class ShareError(Exception):
    pass


Opener = Callable[[urllib.request.Request], Any]


def _default_open(req: urllib.request.Request) -> Any:
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def _call(method: str, path: str, token: str, *, body: Optional[bytes] = None, ctype: str = "application/json",
          opener: Opener = _default_open) -> tuple[int, Any]:
    req = urllib.request.Request(HUB + path, data=body, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": ctype,
                                          "User-Agent": "ichor-hermes-plugin"})
    try:
        with opener(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read() or b"{}")
        except ValueError:
            detail = {}
        return err.code, detail


def _hf_token() -> str:
    """Read the token through Hermes's profile-scoped secret route (catalog rule 11), never os.environ."""
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return ""
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        try:
            value = get_secret(name)
        except Exception:  # unscoped under multiplexing: fail closed
            return ""
        if value:
            return value
    return ""


def share(pairs: list[dict[str, Any]], *, token: Optional[str] = None, repo_name: str = "ichor-pairs",
          private: bool = True, opener: Opener = _default_open) -> tuple[str, int]:
    """Upload pairs as one new JSONL file. Returns (dataset_url, rows). Raises ShareError with a user message."""
    token = token or _hf_token()
    if not token:
        raise ShareError("sharing needs a Hugging Face token\nadd HF_TOKEN to ~/.hermes/.env, then /ichor share")
    if not pairs:
        raise ShareError("nothing queued to share\nreply s on a card, or /ichor share <id>")

    status, who = _call("GET", "/api/whoami-v2", token, opener=opener)
    if status != 200 or not isinstance(who, dict) or not who.get("name"):
        raise ShareError("Hugging Face rejected the token\ncheck HF_TOKEN in ~/.hermes/.env")
    repo_id = f"{who['name']}/{repo_name}"

    status, info = _call("POST", "/api/repos/create", token, opener=opener,
                         body=json.dumps({"type": "dataset", "name": repo_name, "private": private}).encode())
    if status == 403:
        raise ShareError("token can't create repos\ngive it write access to your own repos")
    if status not in (200, 201, 409):
        raise ShareError(f"could not create {repo_id} (HTTP {status})")
    needs_card = status in (200, 201)
    if not needs_card:  # repo already existed: add the card only if it has none
        st, meta = _call("GET", f"/api/datasets/{repo_id}", token, opener=opener)
        siblings = meta.get("siblings", []) if st == 200 and isinstance(meta, dict) else []
        needs_card = st == 200 and not any(s.get("rfilename") == "README.md" for s in siblings if isinstance(s, dict))

    rows = "".join(json.dumps(to_record(p), ensure_ascii=False) + "\n" for p in pairs)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    ops = [{"key": "header", "value": {"summary": f"ichor: add {len(pairs)} pairs", "description": ""}}]
    ops.append({"key": "file", "value": {"path": f"data/{stamp}-{len(pairs)}.jsonl", "encoding": "base64",
                                         "content": base64.b64encode(rows.encode()).decode()}})
    if needs_card:
        ops.append({"key": "file", "value": {"path": "README.md", "encoding": "base64",
                                             "content": base64.b64encode(CARD.format(repo=repo_id).encode()).decode()}})
    body = "\n".join(json.dumps(op) for op in ops).encode()
    status, res = _call("POST", f"/api/datasets/{repo_id}/commit/main", token, body=body,
                        ctype="application/x-ndjson", opener=opener)
    if status == 403:
        raise ShareError(f"token can't write to {repo_id}\ngive it write access to your own repos")
    if status not in (200, 201):
        raise ShareError(f"upload to {repo_id} failed (HTTP {status})")
    return f"{HUB}/datasets/{repo_id}", len(pairs)
