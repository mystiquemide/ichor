# Ichor PRD

Every correction is training data.

## 1. Summary

Ichor is a Hermes Agent plugin that notices when you correct Hermes, pairs the rejected answer with the one you accepted, scrubs it locally, and asks you once what to do with it: keep it private, share it to an open Hugging Face dataset, or discard it. Kept pairs export as TRL-ready DPO data and as an Atropos environment, so the moments Hermes gets it wrong become fine-tune and RL material you own.

## 2. Problem

- Every Hermes user corrects the agent many times a day ("no, use pnpm", /retry, /undo). That signal is the most valuable kind of training data (a preference pair from real usage), and today it is lost when the session ends.
- Existing sharing paths export raw transcripts only: Hermes core `sessions export --format trace` plus HF upload (Jul 2026), and traces.com's Hermes adapter (Mar 2026). Neither records which response was wrong and which was right.
- Open model builders say data is the bottleneck. Hugging Face CEO Clem Delangue (Apr 7 2026): "one of the biggest bottlenecks for open-source agent models is the data." Nous builds Hermes models and the Atropos RL framework.
- Demand risk (validated): opt-in donation alone is weak. trace-commons/agent-traces holds about 30 rows. So Ichor's primary value is local and personal; sharing is a one-tap bonus.

## 3. Users

- Primary: Hermes power users who run local or fine-tunable models and want a dataset of their own corrections.
- Secondary: everyday Hermes users who want to see what Hermes keeps getting wrong for them.
- Tertiary: Nous and the open model community, who receive shared, scrubbed preference pairs.

## 4. Goals and non-goals

Goals
- Detect corrections with high precision and always confirm with one human tap.
- Scrub secrets and personal data locally before anything is stored or shown for sharing.
- Produce files that load in standard tooling without edits.

Non-goals (V1)
- Training or fine-tuning models inside Hermes.
- Automatic sharing of anything without a per-pair tap.
- A Desktop pane or web dashboard.
- Any behavior that blocks, changes, or gates what Hermes does. Ichor only observes.

## 5. User stories

1. As a user, when I say "no, do X instead", Ichor captures the previous answer as rejected and the next answer as accepted.
2. As a user, when I run /retry or /undo and get a better answer, Ichor captures that pair.
3. As a user, I see a card showing the pair, what was scrubbed, and buttons for Keep, Share, Discard.
4. As a user, I run /ichor and see counts and my top recurring mistake categories.
5. As a user, I run /ichor export and get DPO JSONL and an Atropos environment folder, with paths and row counts.
6. As a user, I run /ichor share and my approved pairs upload to my Hugging Face dataset; I get the URL.
7. As a user, I can turn Ichor off per session or globally, and delete all stored pairs with one command.

## 6. Functional requirements

| ID | Requirement |
|----|-------------|
| F1 | Observe turns via `post_llm_call` (user_message, assistant_response, conversation_history, model, session_id, turn_id). Store only the last turn per session in memory until a pair forms. |
| F2 | Detect correction signals: (a) explicit correction phrases in the next user message, (b) retry (same user text re-sent after the prior reply was dropped), (c) undo (history shrinks). |
| F3 | Optional judge: with the `llm.side_question` capability granted, ask the session's own agent whether the previous turn was corrected and why, to label a category. Without it, fall back to deterministic rules. |
| F4 | Scrub both sides with local rules: API keys and tokens, emails, home paths, IPs, phone numbers. Record counts per type. |
| F5 | Post a capture card with `ctx.post_message` and edit it in place after the user chooses. Where no live gateway exists (plain CLI), queue the pair as pending and surface it via /ichor review. |
| F6 | Persist pairs in a plugin SQLite store under the plugin data directory, with status pending, kept, shared, or discarded. |
| F7 | /ichor commands: status, review, keep, share, discard, export, off, on, forget-all. |
| F8 | Export TRL DPO JSONL (prompt, chosen, rejected, plus metadata) and an Atropos environment folder (dataset file plus environment module with a reward based on the accepted answer). |
| F9 | Share uploads kept-and-approved pairs to a Hugging Face dataset repo via the Hub HTTP API using HF_TOKEN; private by default, configurable. |

## 7. Non-functional requirements

- Never raises into the agent loop; every hook is fail-open.
- Adds no visible latency to a turn (work happens after the reply).
- No network calls except /ichor share.
- Passes `hermes plugins validate --install-deps` with declared capabilities matching reality.
- No core patching, no undocumented core imports.

## 8. RICE backlog

| # | Item | Reach | Impact | Confidence | Effort (days) | Score |
|---|------|-------|--------|------------|---------------|-------|
| 1 | Correction detection (phrases, retry, undo) | 10 | 3 | 0.8 | 1 | 24 |
| 2 | Local scrubber | 10 | 3 | 0.9 | 0.5 | 54 |
| 3 | Capture card with edit in place | 10 | 3 | 0.7 | 0.5 | 42 |
| 4 | SQLite store and /ichor commands | 10 | 2 | 0.9 | 0.5 | 36 |
| 5 | DPO export with real TRL load test | 6 | 3 | 0.8 | 0.5 | 28.8 |
| 6 | HF share | 4 | 2 | 0.8 | 0.5 | 12.8 |
| 7 | Atropos environment export | 3 | 3 | 0.5 | 1 | 4.5 |
| 8 | side_question category judge | 6 | 2 | 0.5 | 0.5 | 12 |

Must: 1-5. Should: 6, 8. Could: 7. Stretch: Desktop pane.

## 9. KPIs

- Detection precision on a labeled fixture set of at least 40 turns: 90 percent or better.
- Scrubber recall on a secrets fixture set: 100 percent for listed token formats.
- Export loads in TRL `DPOTrainer` dataset format without edits.
- Demo: full capture to share loop under 90 seconds on Telegram.

## 10. Risks

| Risk | Mitigation |
|------|-----------|
| False correction labels | Human tap on every pair; precision fixture tests |
| Scrubbing misses something | Local only by default; preview before share; private HF repo default |
| post_message unavailable in plain CLI | Pending queue plus /ichor review |
| Core ships a similar feature | Our value is labeled pairs, not raw export; ship early |
| HF token lacks write scope | Verify with a private test repo during build |

## 11. Out of scope

Training runs, hosted services, payment, team accounts, automatic sharing, dashboards.

## 12. Timeline (deadline Nov 11 2026, 5PM EST)

- Nov 7: PRD, architecture, tasks; detection and scrubber with tests.
- Nov 8: store, card, commands; live test on Telegram.
- Nov 9: export, share, Atropos; validate; public repo.
- Nov 10: polish, README, demo video.
- Nov 11 morning: catalog PR, X post, form.
