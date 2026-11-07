# Ichor tasks

Each task ends with a passing test or a real command run, then a commit.

| # | Task | Depends | Proof |
|---|------|---------|-------|
| 1 | Plugin foundation: plugin.yaml, register(ctx), /ichor status command, observer hook logging turn shapes | none | `hermes plugins validate .` and `hermes plugins doctor .` pass; /ichor replies in a live session |
| 2 | Live signal check on Telegram: text correction, /retry, /undo history shapes recorded | 1 | logged kwargs from real turns; detection rules adjusted to match |
| 3 | scrub.py plus secrets fixture | 1 | pytest 100 percent recall on fixture |
| 4 | detect.py plus 40+ labeled turn fixture | 2 | pytest prints precision, >= 0.9 |
| 5 | state.py and post_llm_call wiring | 4 | unit test with simulated turn sequence |
| 6 | store.py SQLite schema and queries | 1 | pytest |
| 7 | card.py rendering | 6 | pytest snapshot strings |
| 8 | Card delivery via post_message, fallback to pending | 5, 6, 7 | live Telegram test: card appears |
| 9 | Short-reply claiming (k / s / d) via post_gateway_admission, 120 s window | 8 | live Telegram: reply `k` edits card; unrelated `k` outside window reaches agent |
| 10 | /ichor status, review, keep, share, discard, off, on, forget-all | 6, 7 | pytest plus live run |
| 11 | export_dpo.py plus examples/load_with_trl.py | 6 | script loads export through TRL DPO preprocessing and prints a sample |
| 12 | share_hf.py | 6 | real upload to a private test repo, URL opens |
| 13 | judge.py with side_question, fail closed | 5 | unit test with fake ctx; live run with capability granted |
| 14 | export_atropos.py (optional, cut if not done Nov 9) | 11 | env module imports and scores a sample |
| 15 | Validate clean at release SHA | all | command output saved |
| 16 | README, screenshots, catalog yaml draft | 15 | review |
| 17 | Demo recording | 16 | video under 90 s |
| 18 | Public repo, tag v0.1.0, catalog PR, X post, form | 17 | links |

Ongoing from Task 8: dogfood Ichor in real sessions. Target 30+ reviewed real pairs by Nov 10.

Critical path: 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 15.

Order of days:
- Nov 7: 1-7
- Nov 8: 8-11
- Nov 9: 12-15
- Nov 10: 16, 17
- Nov 11 by 12:00 EST: 18
