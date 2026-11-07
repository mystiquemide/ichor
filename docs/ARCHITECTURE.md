# Ichor architecture

Ichor is a native Hermes plugin: `plugin.yaml` plus `__init__.py` exposing `register(ctx)`. It observes finished turns, forms a preference pair when the user rejects an answer, scrubs it, stores it locally, and exports or shares pairs on request. It never changes, blocks or delays what Hermes does.

```
turn N  ── post_llm_call ──▶ TurnState remembers (user, answer, history length)
turn N+1 ─ post_llm_call ──▶ detect(N, N+1) ── no ──▶ done
                                  │ yes
                                  ▼
                 scrub ▶ categorize ▶ store (pending) ▶ post card ▶ open 120 s reply window
                                                            │            (background) side_question label
user replies k / s / d ── post_gateway_admission ──▶ set status ▶ edit card in place
/ichor export ──▶ dpo.jsonl + atropos_env/        /ichor share ──▶ Hugging Face dataset
```

## Hermes surfaces

| Surface | Use |
|---|---|
| `post_llm_call` hook | Every finished turn: `session_id`, `user_message`, `assistant_response`, `conversation_history`, `platform`, `model`, `side_question_token` |
| `on_session_finalize` hook | Drops per-session state. `on_session_end` is not used because it fires after every turn |
| `post_gateway_admission` hook (async) | Claims a one-letter card reply by returning `{"action": "handled"}`; anything else passes through |
| `ctx.post_message` / `handle.aedit` | Posts the card and edits it in place |
| `ctx.side_question` | Optional mistake label, capability `llm.side_question`, fails closed |
| `ctx.register_command("ichor", ...)` | One slash command with subcommands; receives `session_id` and `platform` |
| `plugins.plugin_storage.plugin_db` | Profile-scoped SQLite at `~/.hermes/plugin-data/ichor/ichor.db` |

No core module is patched or imported beyond the documented plugin helpers.

## Modules

| File | Role |
|---|---|
| `__init__.py` | `register(ctx)`, hook handlers, export and share glue |
| `state.py` | Last turn per session (bounded to 256 sessions), per-session off switch, skips cron and subagent turns |
| `detect.py` | `detect(prev, cur)` returns a `Signal` (retry, undo or correction) or `None` |
| `scrub.py` | Pattern scrubber with bounded regexes, returns text plus counts by type |
| `categorize.py` | Local mistake label from the user's words; the side_question label overrides it |
| `judge.py` | Builds the side_question prompt, cleans the answer, runs on a daemon thread |
| `store.py` | SQLite schema, status lifecycle, settings |
| `card.py` | Plain-text card, collapsed line and status views |
| `replies.py` | Reply windows and the claim rule for k / s / d |
| `commands.py` | `/ichor` subcommand router |
| `export_dpo.py` | TRL conversational preference JSONL |
| `export_atropos.py`, `atropos/` | Atropos environment folder and reward |
| `share_hf.py` | Hugging Face Hub upload over stdlib `urllib` |

## Detection

On turn N+1, compared with turn N:

| Kind | Rule | Pair |
|---|---|---|
| retry | Same user text and history did not grow | prompt = u_N, rejected = a_N, accepted = a_N+1 |
| undo | History did not grow and the user text changed | prompt = u_N+1, rejected = a_N, accepted = a_N+1 |
| correction | History grew and the new message opens with a rejection ("no", "wrong", "I said", "that's not", "actually"...) or contains a redirect ("use X instead of Y", "still too long", "didn't work"...) | prompt = u_N, rejected = a_N, accepted = a_N+1, feedback = u_N+1 |

Guards: an unchanged answer makes no pair; a bare "no" or "no thanks" to a question the agent asked is an answer, not a correction; agreement openers ("yes", "let's", "and", "also", "don't worry"), thanks, "no need", question-led requests ("how do I fix it") and "fix it" instructions are skipped; long messages with only a weak cue are low confidence and dropped at the default threshold.

Live history shapes on Hermes v0.23.0: a normal turn grows history by 2 or more; `/retry` re-sends the same text with history unchanged; `/undo` plus a new prompt leaves history unchanged with different text.

## Reply claiming

A message is claimed only if all of these hold: it is exactly `k`, `s`, `d`, `keep`, `share` or `discard` (case-insensitive); it arrives in a direct chat; it is within 120 s of a card; and that card is the only open window on the platform. A plugin can't learn which chat a turn belongs to through public APIs, so this rule is what stops a reply in one chat from settling another chat's pair. `ReplyWindows` already accepts a route key and settles the newest card in the same chat when one is given, ready for a public seam. When nothing matches, the message reaches the agent and `/ichor keep <id>` remains available.

## Storage

```
pairs(id, created_at, session_id, turn_id, platform, model, kind, confidence, reason,
      prompt, rejected, accepted, feedback, category, scrub_counts JSON,
      status pending|kept|shared|discarded, updated_at, uploaded_at, share_url)
settings(key, value)        -- global_off, hf_repo, hf_private
```

## Outputs

- `dpo.jsonl`: `{"prompt": [user], "chosen": [assistant], "rejected": [assistant], "metadata": {...}}`, TRL's conversational preference format.
- `atropos_env/`: `pairs.jsonl`, `ichor_env.py` (`IchorEnv(BaseEnv)`, own tokenizer helper that works on transformers 4 and 5) and `ichor_reward.py` (similarity to accepted minus similarity to rejected, scaled so the accepted answer scores 1 and the rejected one -1).
- Hugging Face: `<user>/ichor-pairs` by default, created private; each share is one commit adding `data/<stamp>-<n>.jsonl`, plus a dataset card on the first share. Pairs are marked uploaded so they are never sent twice.

## Failure behavior

Every hook body is wrapped and fails open. Network is used only by `/ichor share`, with a 30 s timeout, and errors come back as a short message. Each field is cut at 20,000 characters before scrubbing, and the patterns are bounded, so hostile 50k-character inputs scrub in well under a second (`tests/test_scrub_perf.py`). History that drops by more than 6 messages is treated as compression or a reset, never an undo.
