# Ichor architecture

## Overview

Ichor is a native Hermes plugin (`plugin.yaml` plus `__init__.py` exposing `register(ctx)`). It observes turns, forms preference pairs when the user corrects the agent, scrubs them, stores them locally, and exports or shares them on request. It never changes, blocks, or delays agent behavior.

```
  user turn N        post_llm_call(N)          user turn N+1           post_llm_call(N+1)
  ----------> agent ---------------> Ichor ----------> agent ----------------> Ichor
                                     |  remember last turn                      |
                                     |                                          v
                                     |                          detector: correction? retry? undo?
                                     |                                          |
                                     |                          pair = (prompt, rejected=N, accepted=N+1)
                                     |                                          |
                                     |                          scrubber -> store(pending) -> card
                                     v                                          |
                               /ichor commands  <---------------- keep / share / discard
                                     |
                      export: dpo.jsonl, atropos env    share: HF dataset (HTTP API)
```

## Hermes surfaces used

| Surface | Use |
|---------|-----|
| `ctx.register_hook("post_llm_call", fn)` | Observe each finished turn. Kwargs: session_id, turn_id, user_message, assistant_response, conversation_history, model, platform, side_question_token. |
| `ctx.register_hook("on_session_end", fn)` | Drop in-memory turn state for the session. |
| `ctx.register_command("ichor", fn)` | One slash command with subcommands. |
| `ctx.register_hook("post_gateway_admission", fn)` | Claim one-character card replies (k / s / d) inside an open card window. |
| `ctx.post_message(text)` / `handle.edit(text)` | Capture card, edited in place after a choice. |
| `ctx.side_question(token, prompt)` | Optional category label. Capability `llm.side_question`, fail closed. |
| `plugins.plugin_storage.plugin_data_dir` / `plugin_db` | Durable profile-scoped data dir and SQLite. Documented helpers. |

No core module imports beyond documented plugin helpers. No tool overrides.

## Modules

```
ichor/
  plugin.yaml
  __init__.py        register(ctx): wires hooks and the command
  state.py           per-session last-turn memory (bounded dict, thread-safe)
  detect.py          correction signals -> Signal(kind, confidence, reason)
  scrub.py           regex scrubber -> (text, counts)
  store.py           SQLite schema and queries
  card.py            card text rendering (pure functions)
  commands.py        /ichor subcommand router
  export_dpo.py      TRL DPO JSONL writer
  export_atropos.py  Atropos environment folder writer
  share_hf.py        HF Hub HTTP upload (stdlib urllib only)
  judge.py           optional side_question category labeler
tests/
  fixtures/turns.jsonl      labeled correction / non-correction turns
  fixtures/secrets.txt      token formats for scrubber recall
  test_detect.py test_scrub.py test_store.py test_export.py test_commands.py
```

## Detection

Input on turn N+1: previous turn (u_N, a_N, history_len_N) and current turn (u_N1, a_N1, history_len_N1).

| Kind | Rule | Confidence |
|------|------|-----------|
| retry | normalized u_N1 == normalized u_N and history_len_N1 <= history_len_N | high |
| undo | history_len_N1 < history_len_N - 1 (turns removed) and u_N1 differs | medium; prompt = u_N1, rejected = a_N |
| correction | u_N1 starts with or contains a correction pattern ("no,", "nope", "wrong", "that's not", "instead", "actually", "use X not Y", "don't", "stop", "you forgot") and a_N exists | medium; boosted if short (< 200 chars) |
| none | anything else | n/a |

Guards: skip if a_N is empty, if either side is a tool-only turn with no text, if platform is cron or subagent, or if Ichor is off for the session.

Pair shape:
- retry: prompt = u_N, rejected = a_N, accepted = a_N1
- correction: prompt = u_N, rejected = a_N, accepted = a_N1, feedback = u_N1
- undo: prompt = u_N1, rejected = a_N, accepted = a_N1

Every pair is pending until the user taps. Detection precision is measured against tests/fixtures/turns.jsonl.

## Scrubbing

Applied to prompt, rejected, accepted, feedback before storage. Patterns: OpenAI/Anthropic/HF/GitHub/AWS/Slack/Stripe key formats, generic `Bearer` and `key=` assignments, JWTs, private key blocks, emails, IPv4, phone numbers, home paths (`/home/<user>`, `/Users/<user>`, `C:\Users\<user>`). Replacements are typed placeholders such as `[REDACTED:hf_token]` and `~/`. Counts per type are stored and shown on the card.

## Storage

SQLite at `plugin_db("ichor", "ichor.db")`.

```
pairs(
  id INTEGER PRIMARY KEY,
  created_at TEXT, session_id TEXT, turn_id TEXT, platform TEXT, model TEXT,
  kind TEXT,                 -- retry | correction | undo
  confidence REAL,
  prompt TEXT, rejected TEXT, accepted TEXT, feedback TEXT,
  category TEXT,             -- judge label or rule label
  scrub_counts TEXT,         -- JSON
  status TEXT,               -- pending | kept | shared | discarded
  shared_at TEXT, share_url TEXT
)
settings(key TEXT PRIMARY KEY, value TEXT)
```

## Commands

| Command | Result |
|---------|--------|
| `/ichor` or `/ichor status` | counts by status, top categories |
| `/ichor review` | next pending pair with choices (ask_choice where supported) |
| `/ichor keep|share|discard <id>` | set status |
| `/ichor export [dir]` | writes `dpo.jsonl` and `atropos_env/`, prints paths and counts |
| `/ichor share` | uploads status=shared pairs not yet uploaded, prints dataset URL |
| `/ichor off|on` | per session toggle; `/ichor off --global` persists |
| `/ichor forget-all` | deletes all pairs after confirmation |

## Card delivery

1. After a pair is stored, call `ctx.post_message(card_text)`.
2. If the handle is ok, keep handle in memory keyed by pair id and open a 120 s reply window for that session.
3. Short replies: a `post_gateway_admission` hook claims an inbound message only when all hold: the session has an open card window, the text is exactly `k`, `s`, or `d` (case-insensitive, trimmed), and a pair is pending. It returns `{"action": "handled"}` and edits the card in place. Anything else passes through to the agent untouched (fail-open).
4. Fallback: `/ichor keep|share|discard <id>` always works, on every surface.
5. If post_message is refused (no live gateway, plain CLI), the pair stays pending and `/ichor review` surfaces it.

## Export formats

DPO JSONL, one object per kept or shared pair:
```
{"prompt": [{"role":"user","content": "..."}], "chosen": [{"role":"assistant","content":"..."}], "rejected": [{"role":"assistant","content":"..."}], "metadata": {"kind":"...", "category":"...", "model":"...", "source":"ichor"}}
```
This is TRL's conversational preference format; verified by loading with `datasets` and running TRL's DPO dataset preprocessing in a test.

Atropos env folder: `pairs.jsonl` plus `ichor_env.py` implementing a BaseEnv subclass that serves prompts and scores completions by similarity to the accepted answer and dissimilarity to the rejected one. Marked experimental.

## Sharing

- Target repo: `<hf_user>/ichor-pairs` (configurable), created private by default via `POST /api/repos/create` with `type: dataset`.
- Upload via the Hub commit API (`POST /api/datasets/{repo}/commit/main`, NDJSON) with `data/<date>-<n>.jsonl` and a dataset card README on first upload.
- Token: `HF_TOKEN` from environment. Missing token returns a setup message, never an error.
- stdlib `urllib` only, no new dependency.

## Error handling

- Every hook body is wrapped; exceptions are logged at debug and swallowed.
- Store writes are short transactions; WAL mode.
- Network only in share; timeouts 30 s; failures reported in command output.

## Configuration

`config_schema` keys: `enabled` (bool, default true), `min_confidence` (low|medium|high, default medium), `use_judge` (bool, default true when capability granted), `hf_repo` (string, default `ichor-pairs`), `hf_private` (bool, default true).

## Testing

- Unit tests per module with pytest, run with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- Fixture-driven precision test for detection.
- Export test loads output through `datasets` and TRL's DPO preprocessing (dev dependency only).
- `hermes plugins validate . --install-deps` and `hermes plugins doctor .` must pass.
- Live test on Telegram gateway before demo.

## ADRs

1. Observe only, via post_llm_call. Keeps Ichor fail-safe and out of the agent's critical path.
2. Human tap on every pair. Precision over recall; protects dataset quality and privacy.
3. Local regex scrubbing, not core redaction. Avoids undocumented core imports; predictable and testable.
4. stdlib HTTP for HF. No dependency floor issues with Hermes core constraints.
5. One slash command with subcommands. Smaller surface, easier to declare and validate.
