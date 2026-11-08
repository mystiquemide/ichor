# ichor

[![ci](https://github.com/mystiquemide/ichor/actions/workflows/ci.yml/badge.svg)](https://github.com/mystiquemide/ichor/actions/workflows/ci.yml)

Every correction is training data.

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin. When you correct Hermes, in the CLI or in a gateway chat like Telegram, Ichor pairs the answer you rejected with the one you accepted, scrubs it on your machine, and asks you once what to do with it. Kept pairs export as TRL preference data and as an environment for [Atropos](https://github.com/NousResearch/atropos), Nous Research's RL framework, so the corrections you give Hermes can train the next model you run under it.

```
you        one-line command to show disk usage of the current folder
hermes     du -sh .
you        no, make it human readable and sorted by size
ichor      ichor · captured pair #4
           you said: "no, make it human readable and sorted by size"
           rejected
             du -sh .
           accepted
             du -sh * | sort -h
           scrubbed: 0 paths · 0 secrets
           reply k keep · s share · d discard
hermes     du -sh * | sort -h
you        k
ichor      ichor · pair #4 kept (private)
```

That exchange is real, captured on Telegram with Hermes v0.23.0.

## Why you'd want it

Every "no, use pnpm", every Hermes `/retry`, every `/undo` followed by a better ask is a labeled preference pair: a prompt, a bad answer, and the answer you wanted. That is the data DPO and reward models train on. Hermes already keeps your sessions and can export traces, but nothing in a trace says which answer you rejected, so that signal is lost when the session ends.

Ichor keeps it, with no extra work from you:

- See what Hermes keeps getting wrong for you. `/ichor` lists your top mistake types.
- Fine-tune your own local model on your own corrections. `/ichor export` writes a file TRL loads as is.
- Run RL against your real failure cases. The same export includes an Atropos environment.
- Share with the open-model community if you choose. `/ichor share` uploads to your own Hugging Face dataset, private by default.

## Install

Needs Hermes v0.23.0 or newer.

```bash
hermes plugins install mystiquemide/ichor   # `hermes plugins install ichor` once the catalog entry is merged
hermes plugins enable ichor
```

That's it. The gateway picks the plugin up without a restart. Correct Hermes once in a direct chat and a card appears. To stop it, `hermes plugins disable ichor`, or `/ichor off` for one chat.

Ichor is per profile, like the rest of Hermes: each profile in `~/.hermes/profiles/<name>/` keeps its own pairs and settings in its own plugin data directory.

Optional:

- For `/ichor share`, add a Hugging Face token with write access to your own repos: `HF_TOKEN=hf_...` in `~/.hermes/.env`.
- `hermes plugins enable` asks once for the `llm.side_question` capability, Hermes's consent gate for plugins that talk to your agent. With it, Ichor asks your agent for a 2 to 4 word mistake label after each captured pair: one short call per pair, never per turn. Say no and Ichor labels mistakes locally from your own words.

## Using it

| You do | Ichor does |
|---|---|
| Correct Hermes ("no, use pnpm", "I said...", "that's the wrong one") | Pairs the previous answer (rejected) with the next one (accepted) and posts a card |
| `/retry` and get a different answer | Same, marked as a retry |
| `/undo` and ask again | Pairs the undone answer with the new one |
| Reply `k`, `s` or `d` to the card | Keeps it, queues it to share, or drops it. The card edits itself in place, and the letter never reaches Hermes |

| Command | What it does |
|---|---|
| `/ichor` | Counts and your top mistake types |
| `/ichor review` | Shows the oldest pending pair |
| `/ichor keep <id>` / `share <id>` / `discard <id>` | Set a pair's status from any surface |
| `/ichor export` | Write `dpo.jsonl` for TRL and an `atropos_env/` folder |
| `/ichor share` | Upload queued pairs to Hugging Face |
| `/ichor set repo <name>` / `set public` / `set private` | Choose the dataset name and visibility for new repos |
| `/ichor off` / `on` | Pause or resume in this chat, add `--global` for everywhere |
| `/ichor forget-all yes` | Delete every stored pair |

## What it produces

`/ichor export` writes to `~/.hermes/plugin-data/ichor/exports/<stamp>/`:

```
dpo.jsonl            {"prompt": [user], "chosen": [assistant], "rejected": [assistant], "metadata": {...}}
atropos_env/
  pairs.jsonl
  ichor_env.py       IchorEnv(BaseEnv): samples completions, scores them against your pair
  ichor_reward.py    +1 for your accepted answer, -1 for the rejected one
```

Run the examples on your own export to see it work end to end:

```bash
pip install -r examples/requirements.txt
python examples/load_with_trl.py  <export>/dpo.jsonl
python examples/train_one_step.py <export>/dpo.jsonl
python examples/atropos_smoke.py  <export>/atropos_env     # needs NousResearch/atropos installed
```

On six pairs captured on Telegram and the CLI, `train_one_step.py` runs DPOTrainer on CPU with TRL's tiny test model (about 5 minutes, under 2.5 GB of memory), and the loss falls on every step:

```
DPOTrainer ran 8 step(s) on 6 Ichor pairs. losses: [0.6931, 0.6762, 0.6615, 0.6496, 0.6396, 0.6315, 0.6254, 0.6215]
```

The Atropos environment scores rollouts without an inference server:

```
  accepted answer   reward +1.00  tokens 62  trained 18
  rejected answer   reward -1.00  tokens 67  trained 23
  unrelated answer  reward -0.05  tokens 54  trained 10
```

This proves the format and the pipeline. Six pairs on a tiny model don't teach anything useful. That takes many real pairs.

## Reliability

Ichor sits in every turn, so it is built to never get in the way.

- It only observes. Every hook is wrapped and fails open: if Ichor errors, Hermes carries on as if it weren't installed.
- It stays fast. Detection and scrubbing take milliseconds, input over 20,000 characters is cut first, and the patterns are bounded so hostile 50k-character text can't stall a turn. The optional label runs on a background thread. The only wait is posting the card itself.
- Short replies are claimed only in direct chats, only within 120 seconds of a card, only for the exact words `k`, `s`, `d`, `keep`, `share` or `discard`, and only while that card is the single one open on the platform. Anything else reaches Hermes untouched. Group chats are never touched.
- History that shrinks a lot (context compression, a reset) is never read as an undo.
- An answer that comes back unchanged after a correction makes no pair.
- Cron and subagent turns are ignored.
- Sharing twice never uploads a pair twice.

Detection precision:

| Set | Hits | Real corrections | Precision |
|---|---|---|---|
| Labeled test fixture, 51 turns (rules tuned here) | 27 | 27 | 1.00 |
| Held-out half of 1,619 real turn pairs from my own Hermes history | 25 | 18 | 0.72 |

The held-out number is the one to trust. About one card in four is a false alarm, which is why nothing is kept until you tap. `d` dismisses it. My session data stays on my machine and is not in this repo.

```bash
hermes plugins validate . --install-deps   # every check passes, security scan safe, no core overrides
python -m pytest tests -q                  # all tests pass, no network needed
```

CI runs the tests on Linux, macOS and Windows, and runs the plugin catalog's own `validate --install-deps` gate against Hermes v0.23.0 and Hermes main on every push.

## Privacy

- Every side of a pair is scrubbed before it's stored: API keys and tokens (OpenAI, Anthropic, Hugging Face, GitHub, AWS, Slack, Stripe, Google, Telegram bot), JWTs, Bearer headers, passwords in URLs, `*_KEY=` / `*_SECRET=` / `*_TOKEN=` / `*_PASSWORD=` assignments, private keys, emails, IP addresses, phone numbers and home paths. The card shows what was removed.
- Pairs live in `~/.hermes/plugin-data/ichor/ichor.db`, inside your profile.
- The only network call is `/ichor share`, to `huggingface.co` with your token. New repos are private unless you run `/ichor set public`.

## How it fits into Hermes

A prompt or a skill only runs when you ask for it, and nobody asks in the moment they're annoyed. Ichor runs inside Hermes's turn loop and uses surfaces only a plugin gets, all through the public plugin API with no core patches (`hermes plugins validate` checks this):

| Hermes surface | What Ichor uses it for |
|---|---|
| `post_llm_call` hook | Sees every finished turn and compares it with the last one |
| `ctx.post_message` and `edit` | Posts the card without being asked, then collapses it in place |
| `post_gateway_admission` hook | Catches the one-letter reply before it becomes an agent turn |
| `ctx.side_question` (optional) | Asks the session's own agent to name the mistake |
| Plugin data directory | Durable SQLite store that follows your profile |
| `on_session_finalize` hook | Drops per-session state when a session really ends |
| `ctx.register_command` | The `/ichor` command and its subcommands |

It reads Hermes's own signals: `/retry` re-sends the same message without growing the history, `/undo` rolls history back before a new ask, and a correction is the next message after an answer. Cron, subagent and batch turns are skipped, so only conversations with you produce pairs. Where Hermes can't post a message into the conversation, the pair is still stored and waits for `/ichor review`.

## Limitations

- Detection is rules-based. Precision is 0.72 on held-out real data, and recall isn't measured, so some corrections are missed.
- On Telegram the card lands just above Hermes's reply, because the hook runs before the reply is sent.
- Hermes refuses `llm.side_question` when the agent runs on an external-process provider (for example a CLI subscription bridge). Ichor falls back to local labels.
- Hermes doesn't tell a plugin which chat a turn came from, so short replies switch off while two cards are open on the same platform, for example in a bot several people use. `/ichor keep <id>` always works.
- A discarded pair keeps no text. Kept and shared pairs stay in the local database until you run `/ichor forget-all yes`.
- Scrubbing is pattern-based and can't catch every secret or personal detail. Read the card before you share.
- The Atropos reward is string similarity, which is a weak signal. Treat the environment as a starting point.

## Development

```bash
git clone https://github.com/mystiquemide/ichor ~/.hermes/plugins/ichor
hermes plugins enable ichor
cd ~/.hermes/plugins/ichor && python -m pytest tests -q
```

The plugin has no Python dependencies. TRL, datasets and transformers are only for the examples.

## License

MIT
