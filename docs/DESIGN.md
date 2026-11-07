# Ichor design

## Brand

- Name: ichor (lowercase in product text).
- Tagline: Every correction is training data.
- Voice: quiet, precise, builder to builder. Short lines. No exclamation marks. Never nags.
- Mark: a single gold drop, slightly tilted, with a small notch cut from one edge. Wordmark is lowercase `ichor` in JetBrains Mono, with the drop replacing the dot of the i.

## Color tokens

| Token | Hex | Use |
|-------|-----|-----|
| ink | #0B0C0E | background |
| graphite | #16181C | cards |
| gold | #E8B04B | only for captured state and the mark |
| rejected | #E5484D | rejected side label only |
| accepted | #3DD6B5 | accepted side label only |
| bone | #E9E6DF | text |

No gradients. Gold appears only when something is captured.

## Type

- JetBrains Mono: wordmark, data, card bodies.
- Inter: prose in README and social assets.

## Chat surfaces (plain text, works on Telegram, Discord, CLI)

Cards are plain text so they render the same everywhere. Lines stay under 48 characters for phone width.

Capture card:
```
ichor · captured pair #14
you said: "no, use pnpm not npm"

rejected
  npm install && npm run build
accepted
  pnpm install && pnpm build

scrubbed: 1 path · 0 secrets
reply k keep · s share · d discard
```

Collapsed after choice:
```
ichor · pair #14 kept (private)
```
```
ichor · pair #14 queued to share
```
```
ichor · pair #14 discarded
```

Long sides are trimmed to 6 lines with `… (+N lines)`.

Status (`/ichor`):
```
ichor · 12 kept · 3 shared · 2 pending
top mistakes
  wrong package manager   4
  ignored file path       3
  too verbose             2
/ichor review · export · share
```

Empty state:
```
ichor · no corrections yet
listening for "no…", /retry and /undo
```

Export:
```
ichor · exported 15 pairs
  dpo      ~/.hermes/plugin-data/ichor/exports/dpo.jsonl
  atropos  ~/.hermes/plugin-data/ichor/exports/atropos_env/
```

Share:
```
ichor · shared 3 pairs (private repo)
https://huggingface.co/datasets/<user>/ichor-pairs
```

Missing token:
```
ichor · sharing needs a Hugging Face token
add HF_TOKEN to ~/.hermes/.env, then /ichor share
```

Off:
```
ichor · off for this session
```

## README visual

Header: the gold drop mark on ink, wordmark, tagline. One diagram: turn N, correction, pair, keep or share, export. One screenshot of the Telegram card. No badge walls.

## Demo video (under 90 s)

1. 0-10 s: line on screen: "Every time you correct your agent, that signal disappears."
2. 10-35 s: Telegram on a phone. Hermes answers with npm. User: "no, use pnpm". Card appears.
3. 35-50 s: /retry on another question, second card. Keep one, share one. Cards collapse.
4. 50-70 s: `/ichor export`, then a terminal loading the file with TRL, rows printed.
5. 70-85 s: `/ichor share`, the pair visible in the Hugging Face dataset viewer.
6. 85-90 s: mark fills gold, tagline.

## Rules

- No em dashes anywhere in product text or docs.
- No emojis in cards.
- Product copy never says demo, mock, or stub.
